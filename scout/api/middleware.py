"""Security middleware for scout serve.

Metadata: v1.0.0 | Scout Contributors | 2026-06-15
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse

if TYPE_CHECKING:
    from scout.config import ScoutConfig

_SECURITY_HEADERS_CLS: type[BaseHTTPMiddleware] | None = None
_HTTPS_REDIRECT_CLS: type[BaseHTTPMiddleware] | None = None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith("/graph"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            )
        else:
            response.headers.setdefault("Content-Security-Policy", "default-src 'self'")
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class HttpsRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if getattr(request.app.state, "force_https", False):
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            if proto != "https":
                target = request.url.replace(scheme="https")
                return RedirectResponse(str(target), status_code=301)
        return await call_next(request)


class NoStoreStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def _middleware_registered(app: FastAPI, cls: type) -> bool:
    return any(getattr(entry, "cls", None) is cls for entry in app.user_middleware)


def configure_security_middleware(app: FastAPI, config: ScoutConfig) -> None:
    """Register CORS, HTTPS redirect, and security headers once."""
    global _SECURITY_HEADERS_CLS, _HTTPS_REDIRECT_CLS

    if _SECURITY_HEADERS_CLS is None:
        _SECURITY_HEADERS_CLS = SecurityHeadersMiddleware
    if _HTTPS_REDIRECT_CLS is None:
        _HTTPS_REDIRECT_CLS = HttpsRedirectMiddleware

    origins = [o for o in config.api.cors_origins if o]
    if origins and not _middleware_registered(app, CORSMiddleware):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Hawkeye-Session-Id"],
        )

    if not _middleware_registered(app, HttpsRedirectMiddleware):
        app.add_middleware(HttpsRedirectMiddleware)

    if not _middleware_registered(app, SecurityHeadersMiddleware):
        app.add_middleware(SecurityHeadersMiddleware)
