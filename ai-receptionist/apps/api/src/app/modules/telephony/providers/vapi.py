"""Vapi adapter — the only file in the platform that knows Vapi's wire format.

Payload shapes follow the Vapi server-message documentation (message envelope
with `type`, `call`, `phoneNumber`, `artifact`). They are covered by fixture
tests here and get contract-validated against the live sandbox during the M1
live-call test; any drift is fixed in this file alone.

Webhook auth: Vapi sends the configured server secret verbatim in the
`x-vapi-secret` header (shared-secret scheme, not HMAC) — compared in
constant time.
"""

import hmac
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ValidationFailedError, WebhookSignatureError
from app.modules.telephony.providers.base import (
    AgentDefinition,
    CallEventType,
    NormalizedCallEvent,
    ToolCallRequest,
    VoiceProvider,
)

VAPI_BASE_URL = "https://api.vapi.ai"

_EVENT_MAP = {
    "end-of-call-report": CallEventType.CALL_ENDED,
    "tool-calls": CallEventType.TOOL_CALL,
    "transcript": CallEventType.TRANSCRIPT_UPDATE,
    "status-update": CallEventType.STATUS_UPDATE,
}


class VapiProvider(VoiceProvider):
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.vapi_api_key
        self._webhook_secret = settings.vapi_webhook_secret
        self._public_base_url = settings.public_webhook_base_url.rstrip("/")
        # Vapi imports the number from Twilio on first attach, so it needs the
        # Twilio credentials that own it.
        self._twilio_account_sid = settings.twilio_account_sid
        self._twilio_auth_token = settings.twilio_auth_token

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=VAPI_BASE_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=15,
        )

    def _assistant_payload(self, definition: AgentDefinition) -> dict[str, Any]:
        if not self._public_base_url:
            raise AppError(
                "PUBLIC_WEBHOOK_BASE_URL is not configured — the vendor agent "
                "would have nowhere to send call and tool-call webhooks"
            )
        payload: dict[str, Any] = {
            "name": f"tenant-{definition.tenant_id}",
            "firstMessage": definition.first_message,
            "model": {
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "messages": [{"role": "system", "content": definition.system_prompt}],
                "tools": definition.tools,
            },
            "maxDurationSeconds": definition.max_duration_seconds,
            # Where Vapi posts status updates, tool calls, and the
            # end-of-call report. The secret comes back as x-vapi-secret and
            # is what verify_webhook() checks.
            "server": {
                "url": f"{self._public_base_url}/webhooks/voice/vapi",
                "secret": self._webhook_secret,
            },
            # Without this, tool-call events never reach us and the agent
            # silently answers from the model alone.
            "serverMessages": ["status-update", "tool-calls", "end-of-call-report"],
        }
        if definition.voice_id:
            payload["voice"] = {"voiceId": definition.voice_id}
        return payload

    def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> None:
        if not self._webhook_secret:
            raise WebhookSignatureError("VAPI_WEBHOOK_SECRET not configured")
        received = {k.lower(): v for k, v in headers.items()}.get("x-vapi-secret", "")
        if not hmac.compare_digest(received, self._webhook_secret):
            raise WebhookSignatureError("vapi secret mismatch")

    def parse_event(self, payload: dict[str, Any]) -> NormalizedCallEvent:
        message = payload.get("message") or {}
        raw_type = message.get("type", "")
        event_type = _EVENT_MAP.get(raw_type)
        if event_type is None:
            raise ValidationFailedError(f"unknown vapi message type: {raw_type!r}")

        # Vapi reports call start as a status-update with status "in-progress".
        if event_type is CallEventType.STATUS_UPDATE and message.get("status") == "in-progress":
            event_type = CallEventType.CALL_STARTED

        call = message.get("call") or {}
        to_number = (message.get("phoneNumber") or {}).get("number", "") or (
            call.get("phoneNumber") or {}
        ).get("number", "")
        from_number = (call.get("customer") or {}).get("number", "")

        return NormalizedCallEvent(
            event_type=event_type,
            vendor_call_id=call.get("id", ""),
            to_number=to_number,
            from_number=from_number,
            payload=message,
        )

    async def sync_agent(self, definition: AgentDefinition, *, existing_agent_id: str = "") -> str:
        payload = self._assistant_payload(definition)
        async with self._client() as client:
            if existing_agent_id:
                response = await client.patch(f"/assistant/{existing_agent_id}", json=payload)
                # A stored id can go stale if the assistant was deleted in the
                # Vapi dashboard; fall through to create rather than failing
                # provisioning outright.
                if response.status_code != 404:
                    response.raise_for_status()
                    return str(response.json()["id"])
            response = await client.post("/assistant", json=payload)
            response.raise_for_status()
            return str(response.json()["id"])

    async def attach_number(self, vendor_agent_id: str, e164_number: str) -> str:
        async with self._client() as client:
            # Numbers are imported into Vapi once (from Twilio) and then
            # re-pointed; look before creating so re-provisioning is safe.
            listing = await client.get("/phone-number")
            listing.raise_for_status()
            existing = next((n for n in listing.json() if n.get("number") == e164_number), None)
            if existing:
                response = await client.patch(
                    f"/phone-number/{existing['id']}", json={"assistantId": vendor_agent_id}
                )
                response.raise_for_status()
                return str(existing["id"])

            response = await client.post(
                "/phone-number",
                json={
                    "provider": "twilio",
                    "number": e164_number,
                    "assistantId": vendor_agent_id,
                    "twilioAccountSid": self._twilio_account_sid,
                    "twilioAuthToken": self._twilio_auth_token,
                },
            )
            response.raise_for_status()
            return str(response.json()["id"])

    def extract_tool_calls(self, event: NormalizedCallEvent) -> list[ToolCallRequest]:
        return [
            ToolCallRequest(
                id=raw.get("id", ""),
                name=raw.get("name", ""),
                arguments=raw.get("arguments") or {},
            )
            for raw in event.payload.get("toolCallList") or []
        ]

    def format_tool_results(self, results: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "results": [
                {"toolCallId": tool_call_id, "result": result} for tool_call_id, result in results
            ]
        }
