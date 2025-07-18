# The name of the cookie where the access token is stored.
# This token is typically short-lived (e.g., 15–60 minutes).
# It is used to authenticate the user in most protected routes.
ACCESS_TOKEN_NAME = "access_token"

# The name of the cookie where the refresh token is stored.
# Refresh tokens are long-lived (e.g., days or weeks) and used
# to generate new access tokens without re-authenticating the user.
REFRESH_TOKEN_NAME = "refresh_token"

# Token type label for access tokens.
# This value is embedded inside the JWT payload as `type="access"` 
# and is checked during validation to distinguish token purposes.
ACCESS_TOKEN_TYPE = "access"

# Token type label for refresh tokens.
# Ensures that refresh tokens cannot be misused in endpoints 
# that expect only access tokens (and vice versa).
REFRESH_TOKEN_TYPE = "refresh"

# Common keyword arguments passed to `response.set_cookie()` and
# `response.delete_cookie()` to enforce secure and consistent
# behavior for all auth-related cookies across the application.
#
# These values are applied to both access_token and refresh_token
# and ensure the cookies are:
# - not accessible via JavaScript (httponly)
# - only sent in same-site or top-level navigation requests (samesite)
# - only sent over HTTPS in production (secure)
COOKIE_COMMON_KWARGS = {
    "httponly": True,     # Prevents JavaScript from reading the cookie — crucial for XSS protection
    "samesite": "lax",    # Allows sending cookies only on same-site or top-level GET navigations (CSRF protection)
    "secure": True,       # Ensures cookies are transmitted only over HTTPS (not HTTP) — important in production
}
