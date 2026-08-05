from fastapi import Response

from ...core.settings import settings
from .token_schema import TokenPairResponseSchema


class TokenCookieHandler:
    """Attaches access and refresh tokens as secure HTTP-only cookies to a response."""

    def set_tokens_in_cookies(
        self, response: Response, tokens: TokenPairResponseSchema
    ) -> Response:
        """
        access_token is needed by both /auth/me and every route under /users/*,
        so it has to stay scoped to the whole site ("/", the default when no
        path is given). refresh_token, however, is only ever read by
        /auth/refresh, /auth/logout, and /auth/logout/all, all under /auth,
        so scoping it to path="/auth" means it's never sent on requests to
        /users/* or anywhere else that never needed it, without breaking any
        route that does. logout_handler and logout_all_handler's delete_cookie
        calls must specify the same path, or the browser will treat the delete
        as a different cookie and leave this one behind.
        """
        access_token = tokens.access_token
        refresh_token = tokens.refresh_token

        # Derived from settings (not hardcoded) so the cookie's browser-side
        # lifetime can never drift from the JWT's own actual expiry: a
        # hardcoded value here that outlives the token just wastes a
        # refresh round-trip on an already-rejected cookie, but one that's
        # SHORTER than a JWT expiry an operator configures would delete the
        # cookie and silently log a user out before their token was even
        # expired.
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
            path="/auth"
        )

        return response


token_cookie_handler = TokenCookieHandler()
