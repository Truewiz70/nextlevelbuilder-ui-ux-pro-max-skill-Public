"""Dashboard API: login, and reading/editing the signed-in tenant's own
config. Every route but login requires a bearer token (`core.auth`); every
route scopes to `auth.tenant_id` from that token — there is no endpoint that
takes a tenant id as a path/query parameter, so there is no way to ask for
another tenant's data by guessing an id.
"""

from fastapi import APIRouter, Depends, Request

from app.core.auth import AuthContext, get_current_user, require_role
from app.core.config import Settings
from app.core.util import deep_merge
from app.modules.tenants.login import login as login_user
from app.modules.tenants.repository import (
    create_agent_config_version,
    get_active_agent_config,
    get_tenant,
    update_tenant,
)
from app.modules.tenants.schemas import (
    AgentConfigSummary,
    AgentConfigUpdateRequest,
    LoginRequest,
    LoginResponse,
    TenantSummary,
    TenantUpdateRequest,
    UserSummary,
)

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    settings: Settings = request.app.state.settings
    result = await login_user(
        tenant_slug=body.tenant_slug, email=body.email, password=body.password, settings=settings
    )
    return LoginResponse(
        access_token=result.access_token,
        tenant=TenantSummary.model_validate(result.tenant),
        user=UserSummary.model_validate(result.user),
    )


@router.get("/tenants/me", response_model=TenantSummary)
async def get_my_tenant(auth: AuthContext = Depends(get_current_user)) -> TenantSummary:
    tenant = await get_tenant(auth.tenant_id)
    return TenantSummary.model_validate(tenant)


@router.patch("/tenants/me", response_model=TenantSummary)
async def update_my_tenant(
    body: TenantUpdateRequest, auth: AuthContext = Depends(require_role("admin"))
) -> TenantSummary:
    fields: dict = {}
    if body.timezone is not None:
        fields["timezone"] = body.timezone
    if body.business_hours is not None:
        fields["business_hours"] = body.business_hours
    if body.settings is not None:
        # Deep-merge over the current value (see TenantUpdateRequest's
        # docstring and core.util.deep_merge) rather than replacing it
        # outright — settings nests at least three levels deep in practice
        # (settings.crm.stage_by_outcome.<outcome>), so a shallow merge would
        # silently delete siblings of whatever key the caller named.
        current = await get_tenant(auth.tenant_id)
        fields["settings"] = deep_merge(current.settings, body.settings)
    if not fields:
        return TenantSummary.model_validate(await get_tenant(auth.tenant_id))
    tenant = await update_tenant(auth.tenant_id, **fields)
    return TenantSummary.model_validate(tenant)


@router.get("/tenants/me/agent-config", response_model=AgentConfigSummary)
async def get_my_agent_config(
    auth: AuthContext = Depends(get_current_user),
) -> AgentConfigSummary:
    config = await get_active_agent_config(auth.tenant_id)
    return AgentConfigSummary.model_validate(config)


@router.patch("/tenants/me/agent-config", response_model=AgentConfigSummary)
async def update_my_agent_config(
    body: AgentConfigUpdateRequest, auth: AuthContext = Depends(require_role("admin"))
) -> AgentConfigSummary:
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    config = await create_agent_config_version(auth.tenant_id, **fields)
    return AgentConfigSummary.model_validate(config)
