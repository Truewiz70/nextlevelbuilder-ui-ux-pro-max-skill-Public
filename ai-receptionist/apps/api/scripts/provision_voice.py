"""Connect a tenant to the voice vendor: push its agent config and point its
phone number at it.

This is the link between the database and the phone network. Until it runs,
a tenant exists in our schema but no phone call can reach it.

Usage:
    python scripts/provision_voice.py --slug bright-smile-dental

Idempotent: re-run after any prompt, knowledge, or tool change to push the
update. The vendor-side ids are stored on `phone_numbers`, so re-running
updates the existing agent rather than creating a duplicate.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import admin_session, tenant_session
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.modules.telephony.providers import get_voice_provider
from app.modules.tenants.models import PhoneNumber, Tenant
from app.modules.tenants.service import build_agent_definition

logger = get_logger(__name__)


async def provision(slug: str) -> None:
    settings = get_settings()
    if not settings.public_webhook_base_url:
        raise AppError(
            "PUBLIC_WEBHOOK_BASE_URL is not set — the vendor needs a reachable "
            "URL to send call and tool-call webhooks to"
        )

    async with admin_session() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            raise AppError(f"no tenant with slug {slug!r} — run `make seed` first")
        # Detach so the instance stays usable after the session closes.
        session.expunge(tenant)
        tenant_id = tenant.id

    async with tenant_session(tenant_id) as session:
        numbers = (
            (await session.execute(select(PhoneNumber).where(PhoneNumber.tenant_id == tenant_id)))
            .scalars()
            .all()
        )
        if not numbers:
            raise AppError(f"tenant {slug!r} has no phone number configured")
        for number in numbers:
            session.expunge(number)

    definition = await build_agent_definition(tenant, tenant_id)
    provider = get_voice_provider(settings)

    # One vendor agent per tenant; every number for the tenant points at it.
    existing_agent_id = next((n.vendor_agent_id for n in numbers if n.vendor_agent_id), "")
    vendor_agent_id = await provider.sync_agent(definition, existing_agent_id=existing_agent_id)
    logger.info(
        "agent_synced",
        slug=slug,
        vendor_agent_id=vendor_agent_id,
        updated=bool(existing_agent_id),
        tools=len(definition.tools),
    )

    async with tenant_session(tenant_id) as session:
        for number in numbers:
            vendor_number_id = await provider.attach_number(vendor_agent_id, number.e164)
            await session.execute(
                PhoneNumber.__table__.update()
                .where(PhoneNumber.id == number.id)
                .values(
                    vendor_agent_id=vendor_agent_id,
                    vendor_number_id=vendor_number_id,
                    vendor=settings.voice_provider,
                )
            )
            logger.info("number_attached", e164=number.e164, vendor_number_id=vendor_number_id)

    logger.info(
        "provisioned",
        slug=slug,
        webhook_url=f"{settings.public_webhook_base_url.rstrip('/')}/webhooks/voice/vapi",
        numbers=[n.e164 for n in numbers],
    )


if __name__ == "__main__":
    configure_logging("INFO", json_output=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="tenant slug, e.g. bright-smile-dental")
    args = parser.parse_args()
    asyncio.run(provision(args.slug))
