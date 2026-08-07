# tests/backend/mystic_auth/unit/test_token_cookie_handler_unit.py
import pytest
from backend.mystic_auth.auth.token_logic.token_cookie_handler import (
    token_cookie_handler,
)
from backend.mystic_auth.auth.token_logic.token_schema import TokenPairResponseSchema
from backend.mystic_auth.core.settings import settings
from fastapi.responses import JSONResponse

TOKENS = TokenPairResponseSchema(access_token="access-value", refresh_token="refresh-value")


def _set_cookie_headers(response: JSONResponse) -> list[str]:
    return [value.decode() for key, value in response.raw_headers if key == b"set-cookie"]


def test_refresh_token_cookie_is_scoped_to_auth_path():
    # Regression guard: refresh_token is only ever read by /auth/refresh,
    # /auth/logout, and /auth/logout/all : all under /auth : so it must be
    # scoped there instead of the site-wide default, which would send it to
    # /users/* and every other route that never needed it.
    response = token_cookie_handler.set_tokens_in_cookies(JSONResponse(content={}), TOKENS)

    headers = _set_cookie_headers(response)
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))
    assert "Path=/auth" in refresh_header


def test_access_token_cookie_is_not_path_restricted():
    # access_token is needed by both /auth/me and every /users/* route, so
    # it must remain valid for the whole site : Starlette's default Path=/
    # (not narrowed to /auth like refresh_token below).
    response = token_cookie_handler.set_tokens_in_cookies(JSONResponse(content={}), TOKENS)

    headers = _set_cookie_headers(response)
    access_header = next(h for h in headers if h.startswith("access_token="))
    assert "Path=/;" in access_header


@pytest.mark.parametrize("cookie_name", ["access_token", "refresh_token"])
def test_both_cookies_keep_secure_flags(cookie_name):
    response = token_cookie_handler.set_tokens_in_cookies(JSONResponse(content={}), TOKENS)

    headers = _set_cookie_headers(response)
    header = next(h for h in headers if h.startswith(f"{cookie_name}="))
    assert "HttpOnly" in header
    assert "Secure" in header
    assert "samesite=strict" in header.lower()


def test_cookie_max_ages_are_derived_from_settings_not_hardcoded():
    # Regression guard: these used to be hardcoded (3600 / 2592000) instead
    # of derived from ACCESS_TOKEN_EXPIRE_MINUTES/REFRESH_TOKEN_EXPIRE_MINUTES,
    # so the cookie's browser-side lifetime could silently diverge from the
    # JWT's actual expiry (e.g. an operator raising ACCESS_TOKEN_EXPIRE_MINUTES
    # above 60 would have the cookie deleted before the token itself expired).
    response = token_cookie_handler.set_tokens_in_cookies(JSONResponse(content={}), TOKENS)

    headers = _set_cookie_headers(response)
    access_header = next(h for h in headers if h.startswith("access_token="))
    refresh_header = next(h for h in headers if h.startswith("refresh_token="))

    assert f"Max-Age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in access_header
    assert f"Max-Age={settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60}" in refresh_header
