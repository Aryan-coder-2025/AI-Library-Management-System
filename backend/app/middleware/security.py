import secrets
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Endpoints exempt from CSRF token verification only.
# Layer 1 Origin check continues to apply to these paths.
CSRF_TOKEN_EXEMPT_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/logout",
})


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Safe methods: read-only, no mutation possible
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # ── Layer 1: Origin Validation ───────────────────────────────────────
        # Applied to ALL state-changing requests, including CSRF-exempt paths.
        # Absent Origin header: permitted (non-browser clients, automated scripts).
        # Present Origin header: must match whitelist.
        origin = request.headers.get("origin")
        if origin is not None:
            # Check against ALLOWED_ORIGINS whitelist
            if origin not in settings.ALLOWED_ORIGINS:
                return JSONResponse(
                    status_code=403,
                    content={"detail": f"Request origin '{origin}' is not permitted."},
                )

        # ── Layer 2: CSRF Token Check ────────────────────────────────────────
        # Skipped only for explicitly named exempt paths (login and logout).
        # All other state-changing requests must carry a matching token.
        path = request.url.path
        if path not in CSRF_TOKEN_EXEMPT_PATHS:
            cookie_csrf = request.cookies.get("csrf_token", "")
            header_csrf = request.headers.get("X-CSRF-Token", "")

            if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF verification failed."},
                )

        return await call_next(request)
