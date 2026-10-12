from datetime import UTC, datetime

from fastapi import Request

from ...auth.security.client_ip import get_client_ip


def build_authorization_context(request: Request) -> dict:
    """
    Builds the `context` dict every real authorization check evaluates
    conditions against. Centralized here so IP/time semantics are defined
    exactly once, trusted server-side, for every check.

    `ip_address` comes from auth/security/client_ip.py: the TCP peer by
    default, or the X-Forwarded-For client only if the peer is a
    configured trusted proxy. Never a caller-supplied header trusted
    outright.

    `current_time` is always this backend's own clock (UTC), never
    caller-supplied. The one exception is the authorization-check
    inspection endpoint, which accepts a hypothetical context to answer
    "what would happen if" and bypasses this builder entirely.

    `security_context` starts empty (no MFA/device-trust signals exist
    yet); it's a reserved key for a future trust-signal layer to fill in.
    """
    return {
        "ip_address": get_client_ip(request),
        "current_time": datetime.now(UTC).isoformat(),
        "security_context": {},
    }
