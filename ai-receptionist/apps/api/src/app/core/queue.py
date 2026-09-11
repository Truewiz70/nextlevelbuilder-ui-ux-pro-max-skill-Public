"""Minimal Redis-backed job queue for the async post-call path.

Deliberately simple for M1 (RPUSH/BLPOP, JSON payloads). Jobs must be
idempotent — the consumer may see a job twice after a crash. Retry/backoff
and dead-lettering land in Phase 4 with the first real consumers; if needs
outgrow this, `arq` is the designated replacement behind these two functions.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger

POST_CALL_QUEUE = "queue:post_call"
# Booking confirmations (email + SMS). Separate from post-call so a slow or
# failing notification provider can never delay call classification, and so
# the two can scale independently.
CONFIRMATIONS_QUEUE = "queue:confirmations"
logger = get_logger(__name__)


async def enqueue(redis: Redis, queue: str, job: dict[str, Any]) -> None:
    await redis.rpush(queue, json.dumps(job))
    logger.info("job_enqueued", queue=queue, job_type=job.get("type"))


async def run_worker(
    redis: Redis,
    queue: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    block_seconds: int = 5,
    max_jobs: int | None = None,
) -> None:
    """Consume jobs until cancelled (or `max_jobs`, for tests)."""
    processed = 0
    while max_jobs is None or processed < max_jobs:
        item = await redis.blpop([queue], timeout=block_seconds)
        if item is None:
            continue
        _, raw = item
        job = json.loads(raw)
        try:
            await handler(job)
        except Exception:
            logger.exception("job_failed", queue=queue, job_type=job.get("type"))
        processed += 1
