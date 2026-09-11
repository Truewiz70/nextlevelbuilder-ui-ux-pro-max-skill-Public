"""Tenant lookups.

`resolve_tenant_by_number` runs *before* tenant identity is known, so it uses
the unscoped session; a dedicated SELECT-only RLS policy (migration 0002)
permits number lookup when no tenant context is set. Everything else runs
tenant-scoped.
"""

import uuid

from sqlalchemy import select

from app.core.db import admin_session, tenant_session
from app.core.errors import TenantNotFoundError
from app.modules.tenants.models import AgentConfig, PhoneNumber, Tenant


async def resolve_tenant_by_number(e164: str) -> tuple[Tenant, PhoneNumber]:
    """Map an inbound phone number to its tenant. The entry point of every call."""
    async with admin_session() as session:
        row = (
            await session.execute(
                select(Tenant, PhoneNumber)
                .join(PhoneNumber, PhoneNumber.tenant_id == Tenant.id)
                .where(PhoneNumber.e164 == e164, Tenant.status == "active")
            )
        ).first()
    if row is None:
        raise TenantNotFoundError(f"no active tenant for number {e164}")
    return row.Tenant, row.PhoneNumber


async def get_tenant(tenant_id: uuid.UUID) -> Tenant:
    """Load a tenant by id. Detached from the session so callers can read its
    config (business hours, timezone, settings) after the session closes."""
    async with admin_session() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is None:
            raise TenantNotFoundError(f"no tenant {tenant_id}")
        session.expunge(tenant)
        return tenant


async def get_active_agent_config(tenant_id: uuid.UUID) -> AgentConfig:
    async with tenant_session(tenant_id) as session:
        config = (
            await session.execute(
                select(AgentConfig).where(AgentConfig.tenant_id == tenant_id, AgentConfig.is_active)
            )
        ).scalar_one_or_none()
    if config is None:
        raise TenantNotFoundError(f"tenant {tenant_id} has no active agent config")
    return config
