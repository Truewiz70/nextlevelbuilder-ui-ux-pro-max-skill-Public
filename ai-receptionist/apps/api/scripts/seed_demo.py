"""Seed a demo tenant from a config/tenants YAML file.

Usage:
    python scripts/seed_demo.py ../../config/tenants/example-dental.yaml \
        --number +15550100001

Idempotent: re-running updates nothing if the slug already exists.

Knowledge-base entries in the YAML's `knowledge:` section are embedded via
Voyage and ready for RAG immediately — this step is skipped (not failed)
when VOYAGE_API_KEY isn't configured, so the tenant is still usable for
qualification/callback testing without live embedding credentials.
"""

import argparse
import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import admin_session, tenant_session
from app.core.logging import configure_logging, get_logger
from app.modules.conversation.knowledge import ingest_document
from app.modules.conversation.models import KnowledgeDoc
from app.modules.conversation.providers import get_embedding_provider
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

    knowledge_doc_ids = []
    async with tenant_session(tenant_id) as session:
        session.add(
            AgentConfig(
                tenant_id=tenant_id,
                version=1,
                is_active=True,
                system_prompt=agent_cfg["persona"],
                first_message=agent_cfg["first_message"],
                voice_id=agent_cfg.get("voice_id", ""),
                voice_provider=agent_cfg.get("voice_provider", ""),
                voice_model=agent_cfg.get("voice_model", ""),
                language=agent_cfg.get("language", "en"),
                qualification=doc.get("qualification", []),
                escalation_policy=doc.get("escalation", {"mode": "voicemail_callback"}),
            )
        )
        session.add(PhoneNumber(tenant_id=tenant_id, e164=number))

        for item in doc.get("knowledge", []):
            knowledge_doc = KnowledgeDoc(
                tenant_id=tenant_id, title=item["title"], content=item["content"]
            )
            session.add(knowledge_doc)
            await session.flush()
            knowledge_doc_ids.append(knowledge_doc.id)

    logger.info("tenant_seeded", slug=tenant_cfg["slug"], tenant_id=str(tenant_id), number=number)

    if not knowledge_doc_ids:
        return
    if not get_settings().voyage_api_key:
        logger.warning(
            "knowledge_ingestion_skipped",
            reason="VOYAGE_API_KEY not configured",
            docs=len(knowledge_doc_ids),
        )
        return

    embeddings = get_embedding_provider(get_settings())
    for knowledge_doc_id in knowledge_doc_ids:
        chunk_count = await ingest_document(tenant_id, knowledge_doc_id, embeddings)
        logger.info("knowledge_doc_ingested", doc_id=str(knowledge_doc_id), chunks=chunk_count)


if __name__ == "__main__":
    configure_logging("INFO", json_output=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--number", default="+15550100001")
    args = parser.parse_args()
    asyncio.run(seed(args.config, args.number))
