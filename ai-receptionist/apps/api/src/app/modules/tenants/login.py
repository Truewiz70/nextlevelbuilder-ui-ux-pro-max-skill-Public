"""Dashboard login: resolve tenant by slug, verify password, issue a JWT.

Deliberately thin — JWT signing, password hashing, and the authentication
error hierarchy all live in `core.security`/`core.errors`; this module only
wires tenant+user resolution to them for the one login use case.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import AuthenticationError, TenantNotFoundError
from app.core.security import encode_jwt, verify_password
from app.modules.tenants.models import Tenant, User
from app.modules.tenants.repository import get_tenant_by_slug, get_user_by_email


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    tenant: Tenant
    user: User


async def login(*, tenant_slug: str, email: str, password: str, settings: Settings) -> LoginResult:
    try:
        tenant = await get_tenant_by_slug(tenant_slug)
    except TenantNotFoundError as exc:
        # Folded into the same error as "wrong password": whether a given
        # business slug exists at all shouldn't be distinguishable from a
        # failed login either, by the same email-enumeration logic
        # `get_user_by_email` already applies one level down.
        raise AuthenticationError("invalid email or password") from exc

    user = await get_user_by_email(tenant.id, email)  # raises AuthenticationError itself
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("invalid email or password")

    token = encode_jwt(
        {
            "sub": str(user.id),
            "tenant_id": str(tenant.id),
            "role": user.role,
            "email": user.email,
            "typ": "access",
        },
        secret_key=settings.secret_key,
        expires_in_minutes=settings.access_token_ttl_minutes,
    )
    return LoginResult(access_token=token, tenant=tenant, user=user)
