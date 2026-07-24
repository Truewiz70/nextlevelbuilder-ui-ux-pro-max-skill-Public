"""Post-call worker: classifies outcome/sentiment and writes a one-line
summary via the fast model. Runs off `queue:post_call`; every step is
idempotent so a crash mid-batch is safe to retry.

CRM sync (Phase 6) adds a further idempotent step here — never on the
webhook hot path.

Run: python -m app.workers.post_call
"""

import asyncio
import functools
import uuid
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.db import tenant_session
from app.core.logging import configure_logging, get_logger
from app.core.queue import POST_CALL_QUEUE, run_worker
from app.modules.conversation.pricing import estimate_cost_cents
from app.modules.conversation.providers import get_llm_provider
from app.modules.conversation.providers.base import LLMProvider
from app.modules.conversation.summarization import summarize_call
from app.modules.telephony.models import Call, Transcript

logger = get_logger(__name__)


async def handle_post_call(job: dict[str, Any], *, llm: LLMProvider | None = None) -> None:
    llm = llm or get_llm_provider(get_settings())
    tenant_id = uuid.UUID(job["tenant_id"])
    call_id = uuid.UUID(job["call_id"])

    async with tenant_session(tenant_id) as session:
        call = await session.get(Call, call_id)
        if call is None or call.outcome is not None:
            return  # already processed (or the call vanished) — idempotent no-op
        turns = (
            await session.execute(select(Transcript.turns).where(Transcript.call_id == call_id))
        ).scalar_one_or_none() or []

    result = await summarize_call(turns, llm)
    cost_cents = estimate_cost_cents(result.model, result.input_tokens, result.output_tokens)

    async with tenant_session(tenant_id) as session:
        # WHERE outcome IS NULL keeps this a no-op if another worker already
        # finalized the call between the read above and this write — the
        # only cost of that race is a redundant LLM call, never a bad write.
        await session.execute(
            update(Call)
            .where(Call.id == call_id, Call.outcome.is_(None))
            .values(llm_cost_cents=Call.llm_cost_cents + cost_cents, **result.classification)
        )
    logger.info(
        "post_call_processed",
        tenant_id=str(tenant_id),
        call_id=str(call_id),
        **result.classification,
    )


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    redis = aioredis.from_url(settings.redis_url)
    llm = get_llm_provider(settings)  # constructed once, reused across jobs
    logger.info("post_call_worker_started", queue=POST_CALL_QUEUE)
    try:
        await run_worker(redis, POST_CALL_QUEUE, functools.partial(handle_post_call, llm=llm))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
