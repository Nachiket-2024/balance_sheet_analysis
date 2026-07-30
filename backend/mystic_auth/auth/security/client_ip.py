from fastapi import Request

from ...core.settings import settings

# Empty by default (TRUSTED_PROXY_IPS unset), so every caller falls back to the
# literal TCP peer address exactly as before. Only becomes non-empty in a
# deployment that explicitly configures its reverse proxy's own address(es),
# opting in to trusting X-Forwarded-For.
_TRUSTED_PROXY_IPS = frozenset(
    ip.strip() for ip in settings.TRUSTED_PROXY_IPS.split(",") if ip.strip()
)


def get_client_ip(request: Request) -> str | None:
    """
    Resolves the real client IP for audit logging, rate limiting, and
    authorization context.

    request.client.host is the literal TCP peer: in a direct deployment (no
    reverse proxy) this is already the real client; behind a reverse proxy
    it's the proxy's own address instead. The X-Forwarded-For header is only
    trusted if that TCP peer is itself one of this deployment's configured
    reverse proxies (TRUSTED_PROXY_IPS), otherwise any internet client could
    set X-Forwarded-For to whatever it likes and impersonate any IP. When
    trusted, the left-most entry is used: nginx's proxy_pass appends the real
    client to any X-Forwarded-For it received, so the first entry is the
    original client and any entries after it were appended by closer proxy
    hops.

    Returns None if request.client is unavailable (e.g. a test client with no
    real transport).
    """
    peer_ip = request.client.host if request.client else None

    if not _TRUSTED_PROXY_IPS or peer_ip not in _TRUSTED_PROXY_IPS:
        return peer_ip

    forwarded_for = request.headers.get("x-forwarded-for")
    if not forwarded_for:
        return peer_ip

    return forwarded_for.split(",")[0].strip() or peer_ip
