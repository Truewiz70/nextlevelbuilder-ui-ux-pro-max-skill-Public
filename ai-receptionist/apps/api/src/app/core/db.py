"""Async database engine, sessions, and tenant-scoped RLS sessions.

Multi-tenant isolation is enforced in PostgreSQL via row-level security.
Every tenant-scoped query must run through `tenant_session()`, which sets the
`app.tenant_id` connection variable that the RLS policies check. The
application connects as a non-superuser role (`receptionist_app` in
production) so policies cannot be bypassed.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models. The schema itself is owned by
    Alembic migrations; models map to it and never create tables."""


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Session scoped to one tenant; RLS policies filter on app.tenant_id.

    `SET LOCAL` binds the variable to the enclosing transaction only, so
    pooled connections never leak tenant context between requests.
    """
    factory = get_session_factory()
    async with factory() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
        )
        yield session


@asynccontextmanager
async def admin_session() -> AsyncIterator[AsyncSession]:
    """Unscoped session for cross-tenant operations (tenant lookup, analytics
    rollups, migrations). Use sparingly and never with caller-supplied SQL."""
    factory = get_session_factory()
    async with factory() as session, session.begin():
        yield session


async def check_database() -> bool:
    async with get_session_factory()() as session:
        await session.execute(text("SELECT 1"))
    return True
