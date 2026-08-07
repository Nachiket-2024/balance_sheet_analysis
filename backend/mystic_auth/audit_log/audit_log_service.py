import traceback

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.security.client_ip import get_client_ip
from ..logging.logging_config import get_logger
from .audit_log_repository import audit_log_repository

logger = get_logger(__name__)

# Known event_type values written by the auth handlers/services, kept as
# plain string constants (not an enum) since, unlike Permission, nothing else
# in the app needs to reference these programmatically beyond passing the
# literal string at each call site.
LOGIN_SUCCESS = "login_success"
LOGIN_FAILURE = "login_failure"
LOGOUT = "logout"
LOGOUT_ALL = "logout_all"
SIGNUP = "signup"
OAUTH2_LOGIN_SUCCESS = "oauth2_login_success"
PASSWORD_RESET_REQUESTED = "password_reset_requested"
PASSWORD_RESET_CONFIRMED = "password_reset_confirmed"
ACCOUNT_VERIFICATION_REQUESTED = "account_verification_requested"
ACCOUNT_VERIFIED = "account_verified"
ACCOUNT_LOCKED = "account_locked"
REFRESH_TOKEN_REUSE_DETECTED = "refresh_token_reuse_detected"
SESSION_REVOKED = "session_revoked"           # One specific session ended via the Manage Sessions card
ACCOUNT_DELETED = "account_deleted"           # Soft delete (reversible)
ACCOUNT_PURGED = "account_purged"             # Hard delete (irreversible)
ACCOUNT_REACTIVATED = "account_reactivated"   # Restored from soft delete
POLICY_ASSIGNED = "policy_assigned"
POLICY_REVOKED = "policy_revoked"
USER_ROLE_CHANGED = "user_role_changed"

# Case-insensitive substring denylist for metadata keys that must never be
# persisted verbatim. Applied recursively so a nested dict value is covered
# too. Every current call site only ever passes emails/counts (see call
# sites across auth/*, user_routes/*), so this is a defense-in-depth
# backstop against a future call site accidentally passing something
# sensitive; not a fix for an existing leak.
_SENSITIVE_METADATA_KEY_MARKERS = ("password", "hash", "token", "secret", "cookie", "jwt", "credential")


def _redact_value(key: str, value: object) -> object:
    if any(marker in key.lower() for marker in _SENSITIVE_METADATA_KEY_MARKERS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return _redact_sensitive_metadata(value)
    return value


def _redact_sensitive_metadata(metadata: dict | None) -> dict | None:
    if metadata is None:
        return None

    return {key: _redact_value(key, value) for key, value in metadata.items()}


async def log_security_event(
    event_type: str,
    db: AsyncSession | None,
    *,
    user_email: str | None = None,
    success: bool = True,
    request: Request | None = None,
    metadata: dict | None = None,
) -> None:
    """
    Writes one security audit log row. A logging failure must never break the
    actual auth action it's describing: caught and logged as a warning here,
    never re-raised. Mirrors AuthorizationService._log_decision's reasoning.

    `db=None` is accepted (rather than requiring a real session) purely so
    unit tests can call handlers/services directly without wiring a session
    through every mocked collaborator; a real request always supplies one via
    Depends(database.get_session).
    """
    if db is None:
        return

    try:
        ip_address = None
        user_agent = None
        request_id = None
        if request is not None:
            ip_address = get_client_ip(request)
            user_agent = request.headers.get("user-agent")
            request_id = getattr(request.state, "request_id", None)

        await audit_log_repository.create_entry(
            {
                "user_email": user_email,
                "event_type": event_type,
                "success": success,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "request_id": request_id,
                "event_metadata": _redact_sensitive_metadata(metadata),
            },
            db,
        )
    except Exception:
        logger.warning("Failed to write security audit log entry:\n%s", traceback.format_exc())
