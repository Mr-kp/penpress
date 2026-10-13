"""Security middleware for Private Tailscale and Loopback network isolation.

Enforces:
1. Rejection of untrusted Host headers (allows loopback 127.0.0.1 / localhost,
   Tailscale CGNAT IP 100.121.213.19, *.ts.net, ubuntu).
2. DNS rebinding defenses.
3. Security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, CSP).
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

ALLOWED_HOST_PATTERNS = [
    re.compile(r"^127\.0\.0\.1(:\d+)?$"),
    re.compile(r"^localhost(:\d+)?$"),
    re.compile(r"^\[::1\](:\d+)?$"),
    re.compile(r"^100\.121\.213\.19(:\d+)?$"),
    re.compile(r"^100\.(6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d+\.\d+(:\d+)?$"),  # 100.64.0.0/10 Tailscale CGNAT
    re.compile(r"^[a-zA-Z0-9.-]+\.ts\.net(:\d+)?$"),
    re.compile(r"^ubuntu(:\d+)?$"),
    re.compile(r"^testserver(:\d+)?$"),
]


class PrivateHostValidationMiddleware(BaseHTTPMiddleware):
    """Rejects any request whose Host header does not match private Tailscale or loopback."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host_header = request.headers.get("host", "").strip()

        # Check if host header matches any allowed private pattern
        is_allowed = any(pattern.match(host_header) for pattern in ALLOWED_HOST_PATTERNS)
        if not is_allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden: Untrusted Host header",
                    "detail": "PenPress binds strictly to private loopback and Tailscale network (Rule 1).",
                    "host": host_header,
                },
            )

        response = await call_next(request)

        # Append defensive security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self';"
        )

        return response
