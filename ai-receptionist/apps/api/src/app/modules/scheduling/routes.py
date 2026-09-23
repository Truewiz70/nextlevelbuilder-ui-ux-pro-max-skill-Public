"""Dashboard-facing appointment list + cancellation. Nothing here runs on
the in-call hot path — that's `scheduling/tools.py`, a different module
boundary entirely (voice agent vs. human staff)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.core.auth import AuthContext, get_current_user
from app.core.db import tenant_session
from app.core.util import Page
from app.modules.scheduling.models import Appointment
from app.modules.scheduling.schemas import AppointmentSummary
from app.modules.scheduling.service import cancel_appointment

router = APIRouter()


@router.get("/appointments", response_model=Page[AppointmentSummary])
async def list_appointments(
    auth: AuthContext = Depends(get_current_user),
    status: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[AppointmentSummary]:
    async with tenant_session(auth.tenant_id) as session:
        stmt = select(Appointment).where(Appointment.tenant_id == auth.tenant_id)
        count_stmt = (
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == auth.tenant_id)
        )
        if status:
            stmt = stmt.where(Appointment.status == status)
            count_stmt = count_stmt.where(Appointment.status == status)
        total = (await session.execute(count_stmt)).scalar_one()
        rows = (
            await session.execute(
                stmt.order_by(Appointment.starts_at.desc()).limit(limit).offset(offset)
            )
        ).scalars()
        items = [AppointmentSummary.model_validate(r) for r in rows]
    return Page(items=items, total=total)


@router.post("/appointments/{appointment_id}/cancel", response_model=AppointmentSummary)
async def cancel(
    appointment_id: UUID, request: Request, auth: AuthContext = Depends(get_current_user)
) -> AppointmentSummary:
    calendar = request.app.state.calendar_provider
    appointment = await cancel_appointment(
        tenant_id=auth.tenant_id, appointment_id=appointment_id, calendar=calendar
    )
    return AppointmentSummary.model_validate(appointment)
