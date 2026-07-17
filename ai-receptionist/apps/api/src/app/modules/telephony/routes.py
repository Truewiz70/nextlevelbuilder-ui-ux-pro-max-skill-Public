"""Voice webhook ingress. Verify → normalize → dispatch; nothing else."""

import json

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.core.errors import ValidationFailedError
from app.modules.telephony.providers import get_voice_provider
from app.modules.telephony.service import TelephonyService

router = APIRouter()


@router.post("/vapi")
async def vapi_webhook(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    provider = get_voice_provider(settings)

    body = await request.body()
    provider.verify_webhook(body, dict(request.headers))

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationFailedError("webhook body is not valid JSON") from exc

    event = provider.parse_event(payload)
    service = TelephonyService(request.app.state.redis, settings)
    return await service.handle_event(event)
