"""Escalation: the v1 voicemail-plus-callback path.

There is no live transfer in v1 (Phase 1 decision) — every escalation
trigger (caller asks for a human, out-of-scope question, distress) routes
here, becoming a row the dashboard's callback queue reads (Phase 7).
"""

import uuid

from sqlalchemy import select

from app.core.db import tenant_session
from app.core.errors import NotFoundError, ValidationFailedError
from app.modules.escalation.models import CallbackRequest

# open -> contacted -> resolved (migration 0001's CHECK constraint). Not
# stored as a state machine anywhere else, so this is the one place that
# knows the full set — the dashboard PATCH validates against it directly
# rather than relying on the database CHECK to be the only guard (a 500 from
# a constraint violation is a worse UX than a 422 that names the problem).
VALID_STATUSES = ("open", "contacted", "resolved")


async def create_callback_request(
    *,
    tenant_id: uuid.UUID,
    call_id: uuid.UUID | None,
    caller_e164: str,
    reason: str,
    preferred_window: str | None = None,
    voicemail_transcript: str | None = None,
) -> uuid.UUID:
    async with tenant_session(tenant_id) as session:
        request = CallbackRequest(
            tenant_id=tenant_id,
            call_id=call_id,
            caller_e164=caller_e164,
            reason=reason,
            preferred_window=preferred_window,
            voicemail_transcript=voicemail_transcript,
        )
        session.add(request)
        await session.flush()
        return request.id


async def update_callback_status(
    tenant_id: uuid.UUID, request_id: uuid.UUID, status: str
) -> CallbackRequest:
    if status not in VALID_STATUSES:
        raise ValidationFailedError(f"invalid status {status!r}, must be one of {VALID_STATUSES}")
    async with tenant_session(tenant_id) as session:
        await session.execute(
            CallbackRequest.__table__.update()
            .where(CallbackRequest.id == request_id, CallbackRequest.tenant_id == tenant_id)
            .values(status=status)
        )
        request = (
            await session.execute(select(CallbackRequest).where(CallbackRequest.id == request_id))
        ).scalar_one_or_none()
        if request is None:
            raise NotFoundError(f"no callback request {request_id}")
        session.expunge(request)
        return request
