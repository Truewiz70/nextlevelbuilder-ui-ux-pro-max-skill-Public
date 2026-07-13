"""CalendarProvider — booking backends (Google Calendar first; Cal.com later).

The scheduling module owns availability rules, conflict prevention, and
idempotency; this interface only reads free/busy and writes events. The
calendar is the source of truth for bookings — the local `appointments` row
mirrors it for reporting.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimeSlot:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class BookingRequest:
    tenant_id: uuid.UUID
    slot: TimeSlot
    summary: str
    attendee_name: str
    attendee_phone: str
    attendee_email: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class BookingResult:
    external_event_id: str
    slot: TimeSlot
    confirmed: bool


class CalendarProvider(ABC):
    @abstractmethod
    async def list_available_slots(
        self,
        tenant_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
        duration_minutes: int,
    ) -> list[TimeSlot]:
        """Free slots within the window, already filtered by business hours."""

    @abstractmethod
    async def book(self, request: BookingRequest) -> BookingResult:
        """Create the event. Must re-verify availability atomically and be
        idempotent on `idempotency_key` (retries must not double-book)."""

    @abstractmethod
    async def cancel(self, tenant_id: uuid.UUID, external_event_id: str) -> None: ...
