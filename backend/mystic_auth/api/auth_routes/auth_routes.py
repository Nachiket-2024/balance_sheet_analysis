from fastapi import APIRouter, Cookie, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import SESSION_EVENT_CONNECTION_LIMIT_EXCEEDED, log_security_event
from ...auth.current_user.current_user_handler import current_user_handler
from ...auth.login.login_handler import login_handler
from ...auth.login.login_schema import LoginSchema
from ...auth.logout.logout_handler import logout_handler
from ...auth.logout_all.logout_all_handler import logout_all_handler
from ...auth.manage_sessions.session_list_handler import session_list_handler
from ...auth.manage_sessions.session_revoke_handler import session_revoke_handler
from ...auth.manage_sessions.session_schema import SessionRead
from ...auth.oauth2.oauth2_login_handler import oauth2_login_handler
from ...auth.password_reset_confirm.password_reset_confirm_handler import password_reset_confirm_handler
from ...auth.password_reset_confirm.password_reset_confirm_schema import PasswordResetConfirmSchema
from ...auth.password_reset_request.password_reset_request_handler import password_reset_request_handler
from ...auth.password_reset_request.password_reset_request_schema import PasswordResetRequestSchema

# Honors X-Forwarded-For only from a configured trusted reverse proxy (see auth/security/client_ip.py)
from ...auth.security.client_ip import get_client_ip
from ...auth.security.rate_limiting.rate_limiter_service import rate_limiter_service
from ...auth.signup.signup_handler import signup_handler
from ...auth.signup.signup_schema import SignupSchema
from ...auth.token_logic.jwt_service import jwt_service
from ...auth.verify_account.account_verification_handler import account_verification_handler
from ...auth.verify_account.verify_account_schema import VerifyAccountRequestSchema, VerifyAccountSchema
from ...core.settings import settings
from ...database.connection import database
from ...error_monitoring.sentry_service import capture_security_alert
from ...user_session.session_events import acquire_session_event_lease, session_event_stream

router = APIRouter(prefix="/auth", tags=["Authentication"])

# The OAuth2 routes are always a top-level browser navigation (they return a
# RedirectResponse, never JSON), so rate-limiting them must redirect back to
# the login page too, not render a raw JSON 429 body - see
# rate_limiter_service.rate_limited's redirect_url param.
_OAUTH2_RATE_LIMIT_REDIRECT_URL = f"{settings.FRONTEND_BASE_URL}/login?error=TOO_MANY_ATTEMPTS"


async def _access_token_account_key(kwargs: dict) -> str | None:
    """account_key_func for token-only routes (get_current_user, logout,
    logout_all, list_sessions, revoke_session): none of these has a
    request-body email field, only an access_token cookie. Reads it from a
    declared `access_token` Cookie() param where present, otherwise from
    `request` directly, covering both route styles with one function.

    Uses jwt_service.decode_payload, not verify_token: verifies signature
    and expiry (never trusts a tampered token as an account key) but skips
    verify_token's durable revocation/version checks, since those decide
    whether to let the *request* through, not which rate-limit bucket to
    use. Missing/invalid/expired token returns None, same as any other
    account_key_func miss: the caller falls back to IP-only rate limiting
    instead of failing the request.
    """
    access_token = kwargs.get("access_token")
    if not access_token:
        request = kwargs.get("request")
        access_token = request.cookies.get("access_token") if request else None

    if not access_token:
        return None

    payload = await jwt_service.decode_payload(access_token)
    return payload.get("email") if payload else None


@router.post("/signup")
@rate_limiter_service.rate_limited("signup", account_key_func=lambda kwargs: kwargs["payload"].email)
async def signup(payload: SignupSchema, request: Request, db: AsyncSession = Depends(database.get_session)):
    return await signup_handler.handle_signup(
        payload.name, payload.email, payload.password, db=db, request=request
    )


@router.post("/login")
@rate_limiter_service.rate_limited("login")
async def login(payload: LoginSchema, request: Request, db: AsyncSession = Depends(database.get_session)):
    client_ip = get_client_ip(request) or "unknown"
    return await login_handler.handle_login(
        payload.email, payload.password, client_ip=client_ip, db=db, request=request
    )


@router.get("/oauth2/login/google")
@rate_limiter_service.rate_limited("oauth2_login", redirect_url=_OAUTH2_RATE_LIMIT_REDIRECT_URL)
async def oauth2_login_google():
    return await oauth2_login_handler.handle_oauth2_login_initiate()


@router.get("/oauth2/callback/google")
@rate_limiter_service.rate_limited("oauth2_callback", redirect_url=_OAUTH2_RATE_LIMIT_REDIRECT_URL)
async def oauth2_callback_google(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    oauth_state: str = Cookie(None),
    db: AsyncSession = Depends(database.get_session),
):
    """
    code/state/error are all optional at the route layer (rather than required)
    so a cancelled consent screen or provider-reported error reaches the handler
    as a normal "invalid response" case, redirected cleanly to the frontend
    login page, not a raw FastAPI 422 validation error.
    """
    return await oauth2_login_handler.handle_oauth2_callback(code, state, oauth_state, error, db=db, request=request)


@router.get("/me")
# Read-only, session-cookie-gated (not a credential-guessing target the way
# /auth/login is), yet the highest-frequency authenticated route: the SPA
# calls it on every route mount via useAuthSession. The shared
# MAX_REQUESTS_PER_WINDOW default (100/60s, sized for /auth/login's
# brute-force risk) is real usage-limiting here, not just theoretical: it
# was measured live tripping this exact endpoint 492 times in one local run
# of the full 32-account permission-matrix e2e suite, misread for months as
# a WebKit/Firefox cookie-commit timing race because the failure symptom
# (login succeeds, then "not authenticated" after) looks identical either
# way - see docs/mystic_auth/testing/frontend-e2e.md and
# tests/frontend/mystic_auth/e2e/authorization/permission_matrix_real_accounts_browser.spec.ts.
# A real user with a few tabs open and normal navigation could plausibly
# trip the same default. 300/60s keeps a real bound (still IP- and
# account-keyed, same as every other endpoint here) while giving routine
# multi-tab/multi-navigation usage real headroom.
@rate_limiter_service.rate_limited(
    "get_current_user", account_key_func=_access_token_account_key, max_requests=300, window_seconds=60
)
async def get_current_user(
    request: Request, access_token: str = Cookie(None), db: AsyncSession = Depends(database.get_session)
):
    return await current_user_handler.get_current_user(access_token, db=db, include_active_sessions=True)


@router.get("/session-events")
async def session_events(
    request: Request,
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Server-Sent Events stream: nudges this caller's other open tabs/devices
    the instant their session is revoked (logout-all, password change, a
    targeted Manage Sessions revoke, reuse-detection), instead of each one
    waiting on its next background poll or window-focus refetch to notice.
    See user_session/session_events.py for what actually gets published/sent.

    Not `@rate_limited`: that decorator is built around short request/
    response calls within a rolling window. Long-lived connections are
    instead admitted through a Valkey-backed lease with independent per-
    account and per-IP concurrency caps, so normal reconnects do not consume
    a permanent request budget and a client cannot open unbounded streams.
    """
    current_user = await current_user_handler.get_current_user(access_token, db=db)
    client_ip = get_client_ip(request) or "unknown"
    lease_token = await acquire_session_event_lease(current_user["email"], client_ip)
    if lease_token is None:
        metadata = {
            "account_limit": settings.SESSION_EVENT_MAX_CONNECTIONS_PER_ACCOUNT,
            "ip_limit": settings.SESSION_EVENT_MAX_CONNECTIONS_PER_IP,
        }
        await log_security_event(
            SESSION_EVENT_CONNECTION_LIMIT_EXCEEDED,
            db,
            user_email=current_user["email"],
            success=False,
            request=request,
            metadata=metadata,
        )
        await capture_security_alert(
            SESSION_EVENT_CONNECTION_LIMIT_EXCEEDED,
            metadata=metadata,
        )
        raise HTTPException(status_code=429, detail="Too many session event connections")

    return StreamingResponse(
        session_event_stream(current_user["email"], client_ip, lease_token, access_token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disables response buffering on an nginx-style reverse proxy in
            # front of this app - otherwise events queue up there instead
            # of streaming through as they're published.
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/logout")
@rate_limiter_service.rate_limited("logout", account_key_func=_access_token_account_key)
async def logout(request: Request, db: AsyncSession = Depends(database.get_session)):
    refresh_token = request.cookies.get("refresh_token")
    return await logout_handler.handle_logout(refresh_token, db=db, request=request)


@router.post("/logout/all")
@rate_limiter_service.rate_limited("logout_all", account_key_func=_access_token_account_key)
async def logout_all(request: Request, db: AsyncSession = Depends(database.get_session)):
    refresh_token = request.cookies.get("refresh_token")
    return await logout_all_handler.handle_logout_all(refresh_token, db=db, request=request)


@router.get("/sessions", response_model=list[SessionRead])
@rate_limiter_service.rate_limited("list_sessions", account_key_func=_access_token_account_key)
async def list_sessions(
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(database.get_session),
):
    return await session_list_handler.list_sessions(access_token, refresh_token, db=db)


@router.delete("/sessions/{session_id}")
@rate_limiter_service.rate_limited("revoke_session", account_key_func=_access_token_account_key)
async def revoke_session(
    session_id: int,
    request: Request,
    access_token: str = Cookie(None),
    refresh_token: str = Cookie(None),
    db: AsyncSession = Depends(database.get_session),
):
    return await session_revoke_handler.revoke_session(
        access_token, refresh_token, session_id, db=db, request=request
    )


@router.post("/password-reset/request")
@rate_limiter_service.rate_limited("password_reset_request", account_key_func=lambda kwargs: kwargs["payload"].email)
async def password_reset_request(
    payload: PasswordResetRequestSchema, request: Request, db: AsyncSession = Depends(database.get_session)
):
    return await password_reset_request_handler.handle_password_reset_request(
        payload.email, db=db, request=request
    )


@router.post("/password-reset/confirm")
@rate_limiter_service.rate_limited("password_reset_confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirmSchema, request: Request, db: AsyncSession = Depends(database.get_session)
):
    return await password_reset_confirm_handler.handle_password_reset_confirm(
        payload.token, payload.new_password, db=db, request=request
    )


# POST with the token in the body, not GET with it as a query parameter: a
# token in a URL ends up in browser history, server access logs, and any
# Referer header sent from the post-verification page.
@router.post("/verify-account")
@rate_limiter_service.rate_limited("verify_account")
async def verify_account(
    payload: VerifyAccountSchema, request: Request, db: AsyncSession = Depends(database.get_session)
):
    return await account_verification_handler.handle_account_verification(payload.token, db=db, request=request)


@router.post("/verify-account/request")
@rate_limiter_service.rate_limited("verify_account_request", account_key_func=lambda kwargs: kwargs["payload"].email)
async def verify_account_request(
    payload: VerifyAccountRequestSchema, request: Request, db: AsyncSession = Depends(database.get_session)
):
    return await account_verification_handler.handle_verification_email_request(
        payload.email, db=db, request=request
    )
