"""In-call tool executor: dispatches Vapi tool-call requests to the right
handler and returns spoken-language results within the hot-path latency
budget (<2s target per tool, Phase 1 §3.3). No tool here performs
synchronous external-integration I/O — scheduling and CRM sync land in
Phase 5/6 on the async post-call path.

TOOL_SCHEMAS follows the standard function-calling shape (type/function/
name/description/parameters) Vapi's docs describe; not yet contract-tested
against the live sandbox — verify alongside the Vapi adapter during the M1
live-call test.
"""

import uuid
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger
from app.modules.conversation.faq import answer_faq
from app.modules.conversation.providers.base import EmbeddingProvider, LLMProvider
from app.modules.conversation.qualification import record_answer
from app.modules.escalation.service import create_callback_request
from app.modules.scheduling.providers.base import CalendarProvider
from app.modules.scheduling.tools import (
    COULD_NOT_CHECK,
    handle_book_appointment,
    handle_check_availability,
)
from app.modules.tenants.models import AgentConfig, Tenant

logger = get_logger(__name__)

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "answer_faq",
            "description": (
                "Answer a caller's question using the practice's knowledge base. "
                "Use this for any factual question about the practice — hours, "
                "services, insurance, fees, location — instead of answering from "
                "memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_qualification_answer",
            "description": "Record the caller's answer to one qualification question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The qualification question key"},
                    "answer": {"description": "The caller's answer"},
                },
                "required": ["key", "answer"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Find open appointment times. Call this before offering any "
                "time to the caller — never guess or invent availability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "What the caller wants to come in for",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": (
                            "The caller's preferred date/time in the business's local "
                            "time as ISO 8601, e.g. 2026-09-15T09:00. Omit if they "
                            "have no preference."
                        ),
                    },
                },
                "required": ["service"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": (
                "Book a specific time that check_availability offered. Confirm "
                "the time and the caller's name back to them first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "starts_at": {
                        "type": "string",
                        "description": (
                            "Start time in the business's local time as ISO 8601, "
                            "e.g. 2026-09-15T09:00"
                        ),
                    },
                    "customer_name": {"type": "string"},
                    "customer_email": {
                        "type": "string",
                        "description": "Optional — ask for it to send an email confirmation",
                    },
                },
                "required": ["service", "starts_at", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_callback",
            "description": (
                "Take a voicemail/callback request when the caller asks for a "
                "human, asks something outside what you can help with, or needs "
                "escalation. Collect the caller's name and reason first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "preferred_window": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
]


class ToolExecutor:
    def __init__(
        self,
        llm: LLMProvider,
        embeddings: EmbeddingProvider,
        calendar: CalendarProvider | None = None,
        redis: Redis | None = None,
    ) -> None:
        self._llm = llm
        self._embeddings = embeddings
        # Optional so non-scheduling deployments (and unit tests) need no
        # calendar wiring; the scheduling tools report unavailable instead.
        self._calendar = calendar
        self._redis = redis

    async def dispatch(
        self,
        *,
        tenant: Tenant,
        call_id: uuid.UUID,
        caller_e164: str,
        agent_config: AgentConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        tenant_id = tenant.id
        try:
            match tool_name:
                case "answer_faq":
                    return await answer_faq(
                        tenant_id,
                        call_id,
                        arguments.get("question", ""),
                        self._llm,
                        self._embeddings,
                    )
                case "check_availability":
                    if self._calendar is None:
                        return COULD_NOT_CHECK
                    return await handle_check_availability(
                        tenant=tenant,
                        calendar=self._calendar,
                        service=arguments.get("service", ""),
                        preferred_time=arguments.get("preferred_time"),
                    )
                case "book_appointment":
                    if self._calendar is None or self._redis is None:
                        return COULD_NOT_CHECK
                    return await handle_book_appointment(
                        tenant=tenant,
                        calendar=self._calendar,
                        redis=self._redis,
                        call_id=call_id,
                        service=arguments.get("service", ""),
                        starts_at=arguments.get("starts_at", ""),
                        customer_name=arguments.get("customer_name", ""),
                        customer_phone=caller_e164,
                        customer_email=arguments.get("customer_email"),
                    )
                case "record_qualification_answer":
                    lead_id, score = await record_answer(
                        tenant_id,
                        call_id,
                        caller_e164,
                        arguments.get("key", ""),
                        arguments.get("answer"),
                        agent_config,
                    )
                    logger.info("qualification_answer_recorded", lead_id=str(lead_id), score=score)
                    return "Got it, thank you."
                case "request_callback":
                    request_id = await create_callback_request(
                        tenant_id=tenant_id,
                        call_id=call_id,
                        caller_e164=caller_e164,
                        reason=arguments.get("reason", ""),
                        preferred_window=arguments.get("preferred_window"),
                    )
                    logger.info("callback_requested", request_id=str(request_id))
                    return agent_config.escalation_policy.get(
                        "callback_promise", "Someone from the team will call you back."
                    )
                case _:
                    logger.warning("unknown_tool_call", tool_name=tool_name)
                    return "I'm not able to do that right now, but I can take a message."
        except Exception:
            logger.exception("tool_dispatch_failed", tool_name=tool_name, tenant_id=str(tenant_id))
            return "Sorry, I had trouble with that — let me note it down for the team."
