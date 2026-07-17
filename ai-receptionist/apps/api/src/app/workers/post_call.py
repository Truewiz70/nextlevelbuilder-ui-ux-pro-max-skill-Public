"""Post-call worker (skeleton).

Consumes `queue:post_call`. In M1 it finalizes bookkeeping only; Phase 4
adds the real pipeline (Haiku summary + sentiment, lead scoring) and Phase 6
adds CRM sync — each as an additional idempotent step here, never on the
webhook hot path.

Run: python -m app.workers.post_call
"""

import asyncio
import uuid
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy import update

from app.core.config import get_settings
from app.core.db import tenant_session
from app.core.logging import configure_logging, get_logger
from app.core.queue import POST_CALL_QUEUE, run_worker
from app.modules.telephony.models import Call

logger = get_logger(__name__)


async def handle_post_call(job: dict[str, Any]) -> None:
    tenant_id = uuid.UUID(job["tenant_id"])
    call_id = uuid.UUID(job["call_id"])
    async with tenant_session(tenant_id) as session:
        # Idempotent finalization: only touch calls not yet classified.
        await session.execute(
            update(Call).where(Call.id == call_id, Call.outcome.is_(None)).values(outcome="other")
        )
    logger.info("post_call_processed", tenant_id=str(tenant_id), call_id=str(call_id))


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    redis = aioredis.from_url(settings.redis_url)
    logger.info("post_call_worker_started", queue=POST_CALL_QUEUE)
    try:
        await run_worker(redis, POST_CALL_QUEUE, handle_post_call)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
