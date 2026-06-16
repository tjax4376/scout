"""API authentication dependencies.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from scout.config import AuthConfig, load_config, scout_home

_bearer = HTTPBearer(auto_error=False)


class AuthScope(str, Enum):
    READ = "read"
    ADMIN = "admin"


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    key: str
    admin_key: str
    health_public: bool

    @classmethod
    def from_config(cls, auth: AuthConfig) -> AuthSettings:
        return cls(
            enabled=auth.enabled,
            key=auth.key,
            admin_key=auth.admin_key,
            health_public=auth.health_public,
        )


def load_auth_settings() -> AuthSettings:
    return AuthSettings.from_config(load_config(scout_home()).api.auth)


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def _matches_key(provided: str, expected: str) -> bool:
    if not expected:
        return False
    return secrets.compare_digest(provided, expected)


def _valid_read(settings: AuthSettings, token: str) -> bool:
    if _matches_key(token, settings.key):
        return True
    return _matches_key(token, settings.admin_key)


def _valid_admin(settings: AuthSettings, token: str) -> bool:
    return _matches_key(token, settings.admin_key)


async def require_auth(
    request: Request,
    scope: AuthScope,
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    """Enforce read or admin Bearer auth when enabled."""
    settings: AuthSettings | None = getattr(request.app.state, "auth_settings", None)
    if settings is None:
        settings = load_auth_settings()
    if not settings.enabled:
        return

    if scope is AuthScope.READ and settings.health_public and request.url.path == "/v1/health":
        return

    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")

    if scope is AuthScope.ADMIN:
        if not _valid_admin(settings, token):
            raise HTTPException(status_code=403, detail="forbidden")
        return

    if not _valid_read(settings, token):
        raise HTTPException(status_code=401, detail="unauthorized")


async def require_read_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ],
) -> None:
    await require_auth(request, AuthScope.READ, credentials)


async def require_admin_auth(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer),
    ],
) -> None:
    await require_auth(request, AuthScope.ADMIN, credentials)
