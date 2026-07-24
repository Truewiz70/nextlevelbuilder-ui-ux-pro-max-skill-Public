"""Escalation: the v1 voicemail-plus-callback path.

There is no live transfer in v1 (Phase 1 decision) — every escalation
trigger (caller asks for a human, out-of-scope question, distress) routes
here, becoming a row the dashboard's callback queue reads (Phase 7).
"""

import uuid

from app.core.db import tenant_session
from app.modules.escalation.models import CallbackRequest


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
