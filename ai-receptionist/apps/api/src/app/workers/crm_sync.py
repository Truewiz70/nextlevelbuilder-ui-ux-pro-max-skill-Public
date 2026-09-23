"""CRM worker: pushes a finished call's lead into the tenant's CRM.

Runs off `queue:crm`, enqueued by the post-call worker once a call has been
classified and summarized — so the CRM gets the summary and outcome, not a
bare phone number.

Its own process, separate from post-call and confirmations: a tenant's
HubSpot being down must not stall call classification or delay a confirmation
a customer is waiting on.

Failures propagate to `run_worker`, which retries with backoff and eventually
dead-letters. On dead-letter the ledger row is marked so the failure is
visible in the database, not only in Redis.

Run: python -m app.workers.crm_sync
"""

import asyncio
import functools
import uuid
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

import app.models  # noqa: F401 — registers every ORM model on Base.metadata
from app.core.config import Settings, get_settings
from app.core.errors import PermanentIntegrationError
from app.core.logging import configure_logging, get_logger
from app.core.queue import CRM_QUEUE, DEFAULT_MAX_ATTEMPTS, reclaim_orphans, run_worker
from app.modules.crm.providers import get_crm_provider
from app.modules.crm.providers.base import CRMProvider
from app.modules.crm.service import mark_dead, sync_call
from app.modules.tenants.repository import get_tenant

logger = get_logger(__name__)


@dataclass
class Deps:
    settings: Settings
    crm: CRMProvider


async def handle_crm_sync(job: dict[str, Any], *, deps: Deps) -> None:
    tenant_id = uuid.UUID(job["tenant_id"])
    call_id = uuid.UUID(job["call_id"])
    attempts = int(job.get("attempts", 0))

    tenant = await get_tenant(tenant_id)
    if not (tenant.settings or {}).get("crm", {}).get("enabled", True):
        logger.info("crm_sync_disabled_for_tenant", tenant_id=str(tenant_id))
        return

    try:
        await sync_call(
            tenant=tenant,
            call_id=call_id,
            crm=deps.crm,
            outcome=job.get("outcome"),
            summary=job.get("summary", ""),
            duration_seconds=int(job.get("duration_seconds", 0)),
            service=job.get("service", ""),
        )
    except Exception as exc:
        # This attempt is the last one the queue will make, so record the
        # terminal state here — the worker never sees the dead-letter itself.
        is_last = isinstance(exc, PermanentIntegrationError) or attempts + 1 >= DEFAULT_MAX_ATTEMPTS
        if is_last:
            await mark_dead(tenant_id, call_id, f"{type(exc).__name__}: {exc}")
        raise


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    redis = aioredis.from_url(settings.redis_url)
    deps = Deps(settings=settings, crm=get_crm_provider(settings))
    await reclaim_orphans(redis, CRM_QUEUE)
    logger.info("crm_worker_started", queue=CRM_QUEUE)
    try:
        await run_worker(redis, CRM_QUEUE, functools.partial(handle_crm_sync, deps=deps))
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
