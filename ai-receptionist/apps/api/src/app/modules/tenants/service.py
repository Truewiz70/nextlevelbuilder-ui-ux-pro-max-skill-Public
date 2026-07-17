"""Tenant-facing assembly: turn stored configuration into what the voice
vendor needs. Prompt assembly stays here (platform-owned), never in the
vendor adapter."""

import uuid

from app.core.config import get_settings
from app.modules.telephony.providers.base import AgentDefinition
from app.modules.tenants.models import AgentConfig, Tenant
from app.modules.tenants.repository import get_active_agent_config


def assemble_system_prompt(tenant: Tenant, config: AgentConfig) -> str:
    """Compose the runtime system prompt from tenant config. Guardrails
    (forbidden topics, escalation promise) are part of the prompt contract,
    not optional decoration — they implement the Risk R3 mitigation."""
    forbidden = tenant.settings.get("forbidden_topics", [])
    forbidden_block = (
        "\n\nYou must never discuss: " + "; ".join(forbidden) + ". "
        "If asked, record the question for a callback instead."
        if forbidden
        else ""
    )
    escalation = config.escalation_policy.get(
        "callback_promise", "Someone from the team will call you back."
    )
    return (
        f"{config.system_prompt}{forbidden_block}\n\n"
        f"If the caller asks for a human or you cannot help, take a voicemail: "
        f'collect their name, number, and reason, then say: "{escalation}"'
    )


async def build_agent_definition(tenant: Tenant, tenant_id: uuid.UUID) -> AgentDefinition:
    config = await get_active_agent_config(tenant_id)
    settings = get_settings()
    return AgentDefinition(
        tenant_id=tenant_id,
        system_prompt=assemble_system_prompt(tenant, config),
        first_message=config.first_message,
        voice_id=config.voice_id,
        language=config.language,
        max_duration_seconds=settings.max_call_duration_seconds,
    )
