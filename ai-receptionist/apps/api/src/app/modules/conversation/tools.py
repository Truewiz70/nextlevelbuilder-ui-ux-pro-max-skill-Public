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

from app.core.logging import get_logger
from app.modules.conversation.faq import answer_faq
from app.modules.conversation.providers.base import EmbeddingProvider, LLMProvider
from app.modules.conversation.qualification import record_answer
from app.modules.escalation.service import create_callback_request
from app.modules.tenants.models import AgentConfig

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
    def __init__(self, llm: LLMProvider, embeddings: EmbeddingProvider) -> None:
        self._llm = llm
        self._embeddings = embeddings

    async def dispatch(
        self,
        *,
        tenant_id: uuid.UUID,
        call_id: uuid.UUID,
        caller_e164: str,
        agent_config: AgentConfig,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
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
