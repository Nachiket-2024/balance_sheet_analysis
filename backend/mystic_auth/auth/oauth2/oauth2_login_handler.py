import traceback

from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...audit_log.audit_log_service import OAUTH2_LOGIN_SUCCESS, log_security_event
from ...core.settings import settings
from ...logging.logging_config import get_logger
from ..token_logic.token_cookie_handler import token_cookie_handler
from ..token_logic.token_schema import TokenPairResponseSchema
from .oauth2_service import OAUTH2_STATE_TTL_SECONDS, oauth2_service

logger = get_logger(__name__)


class OAuth2LoginHandler:
    """Drives the Google OAuth2 login flow: initiation and callback handling."""

    def __init__(self):
        self.oauth2_service = oauth2_service

    @staticmethod
    def _redirect_to_login_clearing_state() -> RedirectResponse:
        # Every rejection branch below issues this same redirect; clearing the
        # short-lived oauth_state cookie here (not just on the success path)
        # keeps a cancelled/failed login from leaving it in the browser until
        # its own max_age expiry.
        response = RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/login")
        response.delete_cookie("oauth_state")
        return response

    async def handle_oauth2_login_initiate(self) -> RedirectResponse:
        try:
            google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
            scopes = "openid email profile"
            redirect_uri = settings.GOOGLE_REDIRECT_URI

            state, code_challenge = await self.oauth2_service.generate_and_store_state()

            # No access_type=offline/prompt=consent: this app never stores or uses
            # Google's own refresh_token (see oauth2_service.py's session note), so
            # forcing a persistent offline-access grant and a full consent
            # re-prompt on every login would only widen this app's footprint on
            # the user's Google account for no benefit.
            auth_url = (
                f"{google_auth_url}?response_type=code"
                f"&client_id={settings.GOOGLE_CLIENT_ID}"
                f"&redirect_uri={redirect_uri}"
                f"&scope={scopes.replace(' ', '%20')}"
                f"&code_challenge={code_challenge}"
                f"&code_challenge_method=S256"
                f"&state={state}"
            )

            # SameSite=Lax (not Strict) is required here: this cookie must still be
            # sent when Google redirects the browser back to our callback as a
            # top-level cross-site navigation, which Strict cookies would be
            # dropped from.
            response = RedirectResponse(url=auth_url)
            response.set_cookie(
                key="oauth_state",
                value=state,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=OAUTH2_STATE_TTL_SECONDS,
            )
            return response

        except Exception:
            logger.error("Error initiating OAuth2 login:\n%s", traceback.format_exc())
            return RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/login")

    async def handle_oauth2_callback(
        self,
        code: str | None,
        state: str | None,
        oauth_state_cookie: str | None,
        error: str | None = None,
        db: AsyncSession | None = None,
        request: Request | None = None,
    ) -> RedirectResponse:
        """
        code/state come from Google's redirect query params; error is Google's
        error code (e.g. "access_denied" when the user cancels the consent
        screen). oauth_state_cookie is the state value stored in the short-lived
        cookie set during login initiation, compared against state to guard
        against CSRF/session fixation.
        """
        try:
            # Reject immediately on a provider-reported error (e.g. cancelled
            # consent) or a missing authorization code, before touching
            # state/Redis at all, since neither exists meaningfully in this case.
            if error or not code:
                logger.info("OAuth2 callback did not complete: error=%s, code_present=%s", error, bool(code))
                return self._redirect_to_login_clearing_state()

            if not state or not oauth_state_cookie or state != oauth_state_cookie:
                logger.warning("OAuth2 callback rejected: state/cookie mismatch")
                return self._redirect_to_login_clearing_state()

            code_verifier = await self.oauth2_service.consume_state(state)
            if not code_verifier:
                logger.warning("OAuth2 callback rejected: invalid or expired state")
                return self._redirect_to_login_clearing_state()

            redirect_uri = settings.GOOGLE_REDIRECT_URI

            token_data = await self.oauth2_service.exchange_code_for_tokens(
                code,
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )

            if not token_data or "access_token" not in token_data:
                return self._redirect_to_login_clearing_state()

            access_token_google = token_data["access_token"]

            user_info = await self.oauth2_service.get_user_info(access_token_google)

            if not user_info or "email" not in user_info:
                return self._redirect_to_login_clearing_state()

            # Account creation/linking is keyed entirely on email, so an
            # unverified address would let an attacker who merely controls an
            # inbox-less Google account take over (or get silently linked to) an
            # existing account of the same email. The v3 userinfo endpoint
            # (see oauth2_service.get_user_info) returns this as email_verified,
            # the OIDC-standard claim name -- not verified_email, which is only
            # what the older v2 endpoint used. Treat a missing field the same
            # as False rather than assuming trust.
            if not user_info.get("email_verified"):
                logger.warning(
                    "OAuth2 callback rejected: unverified Google email for %s",
                    user_info.get("email"),
                )
                return self._redirect_to_login_clearing_state()

            jwt_tokens_dict = await self.oauth2_service.login_or_create_user(db, user_info, request=request)

            # login_or_create_user returns None for every rejection case (the
            # reserved system account, a deactivated account, an unexpected
            # error): the audit entry must reflect that outcome instead of
            # unconditionally claiming success, or a blocked takeover attempt
            # against the system account would read as a normal login in the
            # security audit trail.
            if not jwt_tokens_dict:
                await log_security_event(
                    OAUTH2_LOGIN_SUCCESS,
                    db,
                    user_email=user_info.get("email"),
                    success=False,
                    request=request,
                )
                return self._redirect_to_login_clearing_state()

            await log_security_event(
                OAUTH2_LOGIN_SUCCESS,
                db,
                user_email=user_info.get("email"),
                success=True,
                request=request,
            )

            jwt_tokens = TokenPairResponseSchema(**jwt_tokens_dict)
            if not jwt_tokens or not jwt_tokens.access_token:
                return self._redirect_to_login_clearing_state()

            response = RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/dashboard")

            token_cookie_handler.set_tokens_in_cookies(response, jwt_tokens)
            response.delete_cookie("oauth_state")

            return response

        except Exception:
            logger.error("Error handling OAuth2 callback:\n%s", traceback.format_exc())
            return RedirectResponse(url=f"{settings.FRONTEND_BASE_URL}/login")


oauth2_login_handler = OAuth2LoginHandler()
