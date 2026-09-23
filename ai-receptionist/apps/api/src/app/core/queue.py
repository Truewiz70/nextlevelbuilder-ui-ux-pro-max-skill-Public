"""Redis-backed job queue for the async post-call path, with retries,
exponential backoff, and dead-lettering.

## Delivery guarantees, stated plainly

Jobs are **at-least-once**. Every handler must therefore be idempotent — that
is an invariant of this module, not a suggestion, and the reclaim behaviour
below depends on it.

A job moves through three Redis keys:

    queue:<name>            the ready list        (BLMOVE source)
    queue:<name>:processing in-flight             (BLMOVE destination)
    queue:<name>:delayed    ZSET, score = ready-at (retries waiting on backoff)
    queue:<name>:dead       terminal failures, bounded

Taking a job is `BLMOVE ready -> processing`, so a worker that dies mid-job
leaves the payload in `processing` rather than losing it. `reclaim_orphans`
moves anything stranded there back onto the ready list at startup. With more
than one worker on a queue a restart can re-deliver a peer's in-flight job;
idempotent handlers absorb that, which is the trade we are making instead of
per-message visibility timeouts.

## Retry policy

Transient failures (5xx, timeouts, rate limits) are retried with exponential
backoff plus jitter — jitter matters because a vendor outage fails every job
at once and un-jittered backoff would retry them in a thundering herd.

`PermanentIntegrationError` skips retries entirely and dead-letters at once: a
400 from a vendor means the payload is wrong, and sending it five more times
just delays the alert.
"""

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

from app.core.errors import PermanentIntegrationError
from app.core.logging import get_logger

POST_CALL_QUEUE = "queue:post_call"
# Booking confirmations (email + SMS). Separate from post-call so a slow or
# failing notification provider can never delay call classification, and so
# the two can scale independently.
CONFIRMATIONS_QUEUE = "queue:confirmations"
# CRM synchronization. Separate again: a tenant's HubSpot being down must not
# stall confirmations a customer is waiting on.
CRM_QUEUE = "queue:crm"

DEFAULT_MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 300
# The dead-letter list is a diagnostic buffer, not storage. Durable failure
# state belongs in the database (e.g. crm_syncs.status = 'dead').
MAX_DEAD_LETTERS = 1000

logger = get_logger(__name__)


def processing_key(queue: str) -> str:
    return f"{queue}:processing"


def delayed_key(queue: str) -> str:
    return f"{queue}:delayed"


def dead_letter_key(queue: str) -> str:
    return f"{queue}:dead"


async def enqueue(redis: Redis, queue: str, job: dict[str, Any]) -> None:
    await redis.rpush(queue, json.dumps(job))
    logger.info("job_enqueued", queue=queue, job_type=job.get("type"))


def backoff_seconds(attempts: int) -> float:
    """Delay before retry number `attempts` (1-based), with jitter.

    Full jitter rather than a fixed multiplier: an outage fails every job at
    once, and identical backoff would send them all back at the same instant.
    """
    capped = min(BASE_BACKOFF_SECONDS * (2 ** (attempts - 1)), MAX_BACKOFF_SECONDS)
    return random.uniform(capped / 2, capped)


async def schedule_retry(redis: Redis, queue: str, job: dict[str, Any], delay: float) -> None:
    await redis.zadd(delayed_key(queue), {json.dumps(job): time.time() + delay})


async def promote_due_jobs(redis: Redis, queue: str, *, now: float | None = None) -> int:
    """Move retries whose backoff has elapsed back onto the ready list."""
    now = now if now is not None else time.time()
    due = await redis.zrangebyscore(delayed_key(queue), "-inf", now)
    promoted = 0
    for raw in due:
        # Only the worker that wins the ZREM may re-queue the job, so two
        # workers promoting concurrently cannot duplicate it.
        if await redis.zrem(delayed_key(queue), raw):
            await redis.rpush(queue, raw)
            promoted += 1
    return promoted


async def dead_letter(redis: Redis, queue: str, job: dict[str, Any], reason: str) -> None:
    payload = {**job, "dead_reason": reason, "died_at": time.time()}
    await redis.rpush(dead_letter_key(queue), json.dumps(payload))
    await redis.ltrim(dead_letter_key(queue), -MAX_DEAD_LETTERS, -1)
    logger.error(
        "job_dead_lettered",
        queue=queue,
        job_type=job.get("type"),
        attempts=job.get("attempts", 0),
        reason=reason,
    )


async def reclaim_orphans(redis: Redis, queue: str) -> int:
    """Return jobs stranded in `processing` by a crashed worker to the ready
    list. Safe only because handlers are idempotent — see module docstring."""
    reclaimed = 0
    while await redis.rpoplpush(processing_key(queue), queue) is not None:
        reclaimed += 1
    if reclaimed:
        logger.warning("jobs_reclaimed", queue=queue, count=reclaimed)
    return reclaimed


async def run_worker(
    redis: Redis,
    queue: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    block_seconds: int = 5,
    max_jobs: int | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> None:
    """Consume jobs until cancelled (or `max_jobs`, for tests).

    A handler that returns normally completes the job. A handler that raises
    is retried with backoff until `max_attempts`, then dead-lettered —
    except `PermanentIntegrationError`, which dead-letters immediately.
    """
    processed = 0
    while max_jobs is None or processed < max_jobs:
        await promote_due_jobs(redis, queue)

        raw = await redis.blmove(queue, processing_key(queue), timeout=block_seconds)
        if raw is None:
            if max_jobs is not None:
                # Bounded runs must not spin forever on an empty queue.
                break
            continue

        try:
            job = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("job_unparseable", queue=queue)
            await redis.lrem(processing_key(queue), 1, raw)
            await redis.rpush(dead_letter_key(queue), raw)
            processed += 1
            continue

        attempts = int(job.get("attempts", 0)) + 1
        try:
            await handler(job)
        except asyncio.CancelledError:
            # Shutdown, not failure: leave the job in `processing` — a plain
            # `finally` here would remove it unconditionally and defeat
            # crash recovery, since cancellation unwinds through it too.
            # `reclaim_orphans` is what recovers it on the next start.
            raise
        except Exception as exc:
            job = {**job, "attempts": attempts, "last_error": f"{type(exc).__name__}: {exc}"[:500]}
            permanent = isinstance(exc, PermanentIntegrationError)
            if permanent:
                await dead_letter(redis, queue, job, reason="permanent")
            elif attempts >= max_attempts:
                await dead_letter(redis, queue, job, reason="max_attempts")
            else:
                delay = backoff_seconds(attempts)
                await schedule_retry(redis, queue, job, delay)
                logger.warning(
                    "job_retry_scheduled",
                    queue=queue,
                    job_type=job.get("type"),
                    attempts=attempts,
                    delay_seconds=round(delay, 1),
                    error=str(exc)[:200],
                )
            # The job is accounted for (retried or dead) — it must not stay
            # in `processing`, where reclaim would duplicate it.
            await redis.lrem(processing_key(queue), 1, raw)
        else:
            await redis.lrem(processing_key(queue), 1, raw)

        processed += 1
