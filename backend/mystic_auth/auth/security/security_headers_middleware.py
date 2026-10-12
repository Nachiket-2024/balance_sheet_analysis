from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from ...core.settings import settings

# FastAPI's auto-generated /docs and /redoc pages load JS/CSS from a CDN
# (and ReDoc pulls a Google Fonts stylesheet), so the blanket
# `default-src 'none'` CSP below would silently render them as a blank page
# instead of a visible error. /openapi.json is included too since JSON has
# nothing for a CSP to block anyway, so the relaxed policy is harmless there.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})

_DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attaches a fixed set of security-hardening headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # X-Content-Type-Options: nosniff, stops browsers from MIME-sniffing a
        # response into executing as a different content type than declared
        # (e.g. treating a JSON error body as HTML/script).
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options / CSP default-src 'none': this is a JSON API with no
        # HTML pages of its own beyond the auto-generated docs above, so
        # framing and inline scripts/styles are categorically prevented at
        # zero functional cost everywhere else.
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            _DOCS_CSP if request.url.path in _DOCS_PATHS
            else "default-src 'none'; frame-ancestors 'none'"
        )

        # Pins HTTPS for a year (closing the gap before the first secure
        # connection, since production cookies are Secure. Gated on
        # ENVIRONMENT, checked fresh per request, because sending it from a
        # non-production deployment served over plain HTTP would pin HSTS
        # against real traffic with no easy way to undo it.
        if settings.ENVIRONMENT.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # This API never needs the browser to send a Referer header to third
        # parties, and URLs here can carry sensitive query params (e.g. OAuth2
        # state/code during the callback).
        response.headers["Referrer-Policy"] = "no-referrer"

        # This is a JSON API with no page of its own that would ever invoke
        # camera/mic/geolocation/etc.: denying every browser feature closes
        # off a class of clickjacking-adjacent abuse at zero functional cost,
        # same rationale as X-Frame-Options/CSP above.
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )

        # COOP/CORP: this is a same-origin app with no legitimate cross-origin
        # reader, so blocking cross-origin windows/tabs from referencing this
        # one and cross-origin scripts from reading these responses closes off
        # a Spectre-style side-channel at zero functional cost.
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # COEP is skipped on /docs and the other doc paths: it would also
        # require jsdelivr's and Google Fonts' responses to opt in via
        # CORP/CORS, which is out of this app's control.
        if request.url.path not in _DOCS_PATHS:
            response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"

        return response
