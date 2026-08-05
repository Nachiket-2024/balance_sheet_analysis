from datetime import UTC, datetime

from fastapi import Request

from ...auth.security.client_ip import get_client_ip


def build_authorization_context(request: Request) -> dict:
    """
    Builds the `context` dict every real authorization check evaluates
    conditions against (see conditions/network_condition.py,
    conditions/time_condition.py, conditions/date_range_condition.py,
    conditions/security_context_condition.py for what reads each key).
    Centralized here so IP/time semantics are defined exactly once. Every
    authorization check uses the same trusted server-side context builder.

    `ip_address` is resolved via auth/security/client_ip.py: the literal TCP peer
    (request.client.host) by default, or the real client behind
    X-Forwarded-For only if that peer is itself a configured trusted proxy
    (TRUSTED_PROXY_IPS). Never a header/query/body value trusted
    unconditionally, which a caller could set to whatever they like.

    `current_time` always comes from this backend's own clock (UTC, ISO
    8601), never anything the caller supplies. The one documented
    exception is the authorization-check *inspection* endpoint
    (api/pbac_routes/authorization_check_routes.py's check_user_authorization), which
    deliberately accepts a caller-supplied hypothetical context to answer
    "what would happen if": that endpoint never calls this builder, and
    never represents a real access decision.

    `security_context` starts empty: this app does not implement MFA/
    device-trust infrastructure yet, so there is nothing
    trustworthy to populate it with. It exists as a stable, reserved key
    so a future trust-signal layer has exactly one place to feed its
    output into, without changing this function's callers.
    """
    return {
        "ip_address": get_client_ip(request),
        "current_time": datetime.now(UTC).isoformat(),
        "security_context": {},
    }
