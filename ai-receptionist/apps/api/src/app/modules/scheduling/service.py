"""Booking: availability lookup and the write path that cannot double-book.

## Why the database is the mutex

No calendar API offers an atomic "create this event only if the slot is
free". Two callers can both pass an availability check milliseconds apart and
both attempt to book. So the serialization point is our own partial unique
index on (tenant_id, starts_at) for confirmed appointments (migration 0005):

    1. Insert the appointment row first  ← the lock. Loser gets a unique
       violation and is offered alternatives.
    2. Only the winner writes to the calendar.
    3. If the calendar write then fails, the reservation is released so the
       slot does not stay phantom-booked.

Doing it the other way round (calendar first) cannot be serialized, and
failing to release on error is how "ghost" appointments appear.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.db import tenant_session
from app.core.logging import get_logger
from app.modules.scheduling.availability import available_slots
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.providers.base import (
    BookingRequest,
    CalendarProvider,
    TimeSlot,
)
from app.modules.tenants.models import Tenant

logger = get_logger(__name__)


class SlotTakenError(Exception):
    """The slot was booked by someone else between offer and confirmation."""


@dataclass(frozen=True)
class BookingOutcome:
    appointment_id: uuid.UUID
    slot: TimeSlot
    already_existed: bool


async def find_available_slots(
    *,
    tenant: Tenant,
    calendar: CalendarProvider,
    duration_minutes: int,
    window_start: datetime,
    window_end: datetime,
    min_notice_hours: int = 0,
    now: datetime | None = None,
) -> list[TimeSlot]:
    """Calendar busy periods ∪ our own confirmed appointments, subtracted from
    the tenant's business hours.

    Both sources matter: the calendar may hold events booked elsewhere, and
    our own table may hold a booking whose calendar write is still in flight.
    """
    now = now or datetime.now(UTC)
    busy = list(await calendar.list_busy_periods(tenant.id, window_start, window_end))

    async with tenant_session(tenant.id) as session:
        rows = (
            await session.execute(
                select(Appointment.starts_at, Appointment.ends_at).where(
                    Appointment.tenant_id == tenant.id,
                    Appointment.status == "confirmed",
                    Appointment.ends_at > window_start,
                    Appointment.starts_at < window_end,
                )
            )
        ).all()
    busy.extend(TimeSlot(start=r.starts_at, end=r.ends_at) for r in rows)

    return available_slots(
        business_hours=tenant.business_hours,
        timezone=tenant.timezone,
        window_start=window_start,
        window_end=window_end,
        duration_minutes=duration_minutes,
        busy_periods=busy,
        now=now,
        min_notice_hours=min_notice_hours,
    )


async def book_appointment(
    *,
    tenant: Tenant,
    calendar: CalendarProvider,
    call_id: uuid.UUID | None,
    slot: TimeSlot,
    service: str,
    customer_name: str,
    customer_phone: str,
    customer_email: str | None,
    idempotency_key: str,
) -> BookingOutcome:
    """Reserve, then write to the calendar. Raises SlotTakenError if another
    booking won the race."""
    existing = await _find_by_idempotency_key(tenant.id, idempotency_key)
    if existing is not None:
        logger.info("booking_replayed", appointment_id=str(existing))
        return BookingOutcome(appointment_id=existing, slot=slot, already_existed=True)

    # ── 1. Reserve. The unique index decides the winner. ──
    try:
        async with tenant_session(tenant.id) as session:
            appointment = Appointment(
                tenant_id=tenant.id,
                call_id=call_id,
                service=service,
                starts_at=slot.start,
                ends_at=slot.end,
                status="confirmed",
                idempotency_key=idempotency_key,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                timezone=tenant.timezone,
            )
            session.add(appointment)
            await session.flush()
            appointment_id = appointment.id
    except IntegrityError:
        # Either the slot is taken or this exact booking was inserted
        # concurrently; the idempotency lookup distinguishes them.
        replay = await _find_by_idempotency_key(tenant.id, idempotency_key)
        if replay is not None:
            return BookingOutcome(appointment_id=replay, slot=slot, already_existed=True)
        logger.info("slot_taken", tenant_id=str(tenant.id), starts_at=slot.start.isoformat())
        raise SlotTakenError(str(slot.start)) from None

    # ── 2. Calendar write, now that we hold the slot. ──
    try:
        result = await calendar.book(
            BookingRequest(
                tenant_id=tenant.id,
                slot=slot,
                summary=f"{service} — {customer_name}".strip(" —"),
                attendee_name=customer_name,
                attendee_phone=customer_phone,
                attendee_email=customer_email,
                idempotency_key=idempotency_key,
            )
        )
    except Exception:
        # ── 3. Release, so a failed calendar write doesn't hold the slot. ──
        await _release(tenant.id, appointment_id)
        logger.exception("booking_calendar_write_failed", appointment_id=str(appointment_id))
        raise

    async with tenant_session(tenant.id) as session:
        await session.execute(
            Appointment.__table__.update()
            .where(Appointment.id == appointment_id)
            .values(external_event_id=result.external_event_id)
        )

    logger.info(
        "appointment_booked",
        appointment_id=str(appointment_id),
        starts_at=slot.start.isoformat(),
        external_event_id=result.external_event_id,
    )
    return BookingOutcome(appointment_id=appointment_id, slot=slot, already_existed=False)


async def _find_by_idempotency_key(tenant_id: uuid.UUID, key: str) -> uuid.UUID | None:
    async with tenant_session(tenant_id) as session:
        return (
            await session.execute(
                select(Appointment.id).where(
                    Appointment.tenant_id == tenant_id, Appointment.idempotency_key == key
                )
            )
        ).scalar_one_or_none()


async def _release(tenant_id: uuid.UUID, appointment_id: uuid.UUID) -> None:
    """Free the reservation. Status moves out of 'confirmed', which drops it
    from the partial unique index so the slot is immediately rebookable."""
    async with tenant_session(tenant_id) as session:
        await session.execute(
            Appointment.__table__.update()
            .where(Appointment.id == appointment_id)
            .values(status="cancelled", idempotency_key=None)
        )


def default_window(now: datetime, days: int = 14) -> tuple[datetime, datetime]:
    return now, now + timedelta(days=days)
