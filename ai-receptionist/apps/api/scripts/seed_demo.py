"""Seed a demo tenant from a config/tenants YAML file.

Usage:
    python scripts/seed_demo.py ../../config/tenants/example-dental.yaml \
        --number +15550100001

Idempotent: re-running updates nothing if the slug already exists.
"""

import argparse
import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select

from app.core.db import admin_session, tenant_session
from app.core.logging import configure_logging, get_logger
from app.modules.tenants.models import AgentConfig, PhoneNumber, Tenant

logger = get_logger(__name__)


async def seed(config_path: Path, number: str) -> None:
    doc = yaml.safe_load(config_path.read_text())
    tenant_cfg, agent_cfg = doc["tenant"], doc["agent"]

    async with admin_session() as session:
        existing = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_cfg["slug"]))
        ).scalar_one_or_none()
        if existing:
            logger.info("tenant_exists", slug=tenant_cfg["slug"], tenant_id=str(existing.id))
            return
        tenant = Tenant(
            slug=tenant_cfg["slug"],
            name=tenant_cfg["name"],
            vertical=tenant_cfg["vertical"],
            timezone=tenant_cfg.get("timezone", "America/New_York"),
            business_hours=tenant_cfg.get("business_hours", {}),
            settings={"forbidden_topics": agent_cfg.get("forbidden_topics", [])},
        )
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id

    async with tenant_session(tenant_id) as session:
        session.add(
            AgentConfig(
                tenant_id=tenant_id,
                version=1,
                is_active=True,
                system_prompt=agent_cfg["persona"],
                first_message=agent_cfg["first_message"],
                voice_id=agent_cfg.get("voice_id", ""),
                language=agent_cfg.get("language", "en"),
                qualification=doc.get("qualification", []),
                escalation_policy=doc.get("escalation", {"mode": "voicemail_callback"}),
            )
        )
        session.add(PhoneNumber(tenant_id=tenant_id, e164=number))

    logger.info("tenant_seeded", slug=tenant_cfg["slug"], tenant_id=str(tenant_id), number=number)


if __name__ == "__main__":
    configure_logging("INFO", json_output=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--number", default="+15550100001")
    args = parser.parse_args()
    asyncio.run(seed(args.config, args.number))
