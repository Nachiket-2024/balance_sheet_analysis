from fastapi import APIRouter, Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.current_user.current_user_handler import current_user_handler
from ...auth.login.login_handler import login_handler
from ...auth.login.login_schema import LoginSchema
from ...auth.logout.logout_handler import logout_handler
from ...auth.logout_all.logout_all_handler import logout_all_handler
from ...auth.oauth2.oauth2_login_handler import oauth2_login_handler
from ...auth.password_reset_confirm.password_reset_confirm_handler import password_reset_confirm_handler
from ...auth.password_reset_confirm.password_reset_confirm_schema import PasswordResetConfirmSchema
from ...auth.password_reset_request.password_reset_request_handler import password_reset_request_handler
from ...auth.password_reset_request.password_reset_request_schema import PasswordResetRequestSchema

# Honors X-Forwarded-For only from a configured trusted reverse proxy (see auth/security/client_ip.py)
from ...auth.security.client_ip import get_client_ip
from ...auth.security.rate_limiter_service import rate_limiter_service
from ...auth.signup.signup_handler import signup_handler
from ...auth.signup.signup_schema import SignupSchema
from ...auth.verify_account.account_verification_handler import account_verification_handler
from ...auth.verify_account.verify_account_schema import VerifyAccountRequestSchema, VerifyAccountSchema
from ...database.connection import database

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
@rate_limiter_service.rate_limited("oauth2_login")
async def oauth2_login_google():
    return await oauth2_login_handler.handle_oauth2_login_initiate()


@router.get("/oauth2/callback/google")
@rate_limiter_service.rate_limited("oauth2_callback")
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
@rate_limiter_service.rate_limited("get_current_user")
async def get_current_user(
    request: Request, access_token: str = Cookie(None), db: AsyncSession = Depends(database.get_session)
):
    return await current_user_handler.get_current_user(access_token, db=db)


@router.post("/logout")
@rate_limiter_service.rate_limited("logout")
async def logout(request: Request, db: AsyncSession = Depends(database.get_session)):
    refresh_token = request.cookies.get("refresh_token")
    return await logout_handler.handle_logout(refresh_token, db=db, request=request)


@router.post("/logout/all")
@rate_limiter_service.rate_limited("logout_all")
async def logout_all(request: Request, db: AsyncSession = Depends(database.get_session)):
    refresh_token = request.cookies.get("refresh_token")
    return await logout_all_handler.handle_logout_all(refresh_token, db=db, request=request)


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


# POST with the token in the body rather than GET with it as a query parameter : a
# token in a URL ends up in browser history, server access logs, and any Referer
# header sent from the post-verification page.
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
