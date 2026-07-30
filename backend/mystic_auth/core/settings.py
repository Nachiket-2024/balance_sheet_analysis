from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    BACKEND_BASE_URL: str                           # Used to build auth redirect URLs back from the frontend
    FRONTEND_BASE_URL: str                          # Primary frontend origin, used to build redirect/email links (OAuth callback, verification, password reset), and always CORS-allowed
    FRONTEND_ADDITIONAL_BASE_URLS: str = ""          # Optional, comma-separated extra CORS-allowed origins (e.g. a second domain, staging alongside prod). Never used for redirect/email links: those always point at FRONTEND_BASE_URL alone, so there's one canonical link target regardless of how many origins are CORS-allowed.

    DATABASE_URL: str                               # Async PostgreSQL connection URL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    JWT_ALGORITHM: str
    RESET_TOKEN_EXPIRE_MINUTES: int

    GOOGLE_CLIENT_ID: str                           # OAuth2 credentials for Gmail login
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    REDIS_URL: str
    CACHE_DEFAULT_TTL: int                          # Default TTL for Redis cache keys, in seconds

    FROM_EMAIL: str                                 # Email address used to send verification/password-reset emails
    GMAIL_APP_PASSWORD: str                         # Gmail App password for the FROM_EMAIL account
    SUPPORT_EMAIL: str = ""                         # Reply-to/contact address shown in email footers (defaults to FROM_EMAIL if unset)

    SMTP_HOST: str = "smtp.gmail.com"               # SMTP server host (defaulted to Gmail so existing .env files keep working; override to point emails/email_sender.py at another provider)
    SMTP_PORT: int = 587                            # SMTP server port (587 = STARTTLS, Gmail's default)

    APP_NAME: str                                    # Product name shown in email branding and API responses

    LOGIN_LOCKOUT_TIME: int                         # Lockout duration after failed login attempts, in seconds
    MAX_FAILED_LOGIN_ATTEMPTS: int
    LOGIN_LOCKOUT_TIME_PER_IP: int                  # Lockout duration for an IP after too many failed logins across accounts
    MAX_FAILED_LOGIN_ATTEMPTS_PER_IP: int           # Failed attempts from one IP, across any accounts, before that IP is locked out
    MAX_REQUESTS_PER_WINDOW: int                    # Rate limit: max requests per window
    REQUEST_WINDOW_SECONDS: int                     # Rate limit window size, in seconds

    LOG_LEVEL: str = "INFO"                         # Application log level (defaulted so existing .env files/CI keep working)

    ENVIRONMENT: str = "development"                # "development" or "production" (defaulted so existing .env files/CI keep working); gates docs/redoc exposure in main.py

    TRUSTED_PROXY_IPS: str = ""                     # Comma-separated reverse proxy IPs to trust X-Forwarded-For from (see auth/security/client_ip.py). Empty (default) = never trust it, use request.client.host as-is.

    SENTRY_DSN: str = ""                            # Optional. Sentry-protocol error-monitoring DSN (works with Sentry itself, or a self-hosted Sentry-SDK-compatible server like Bugsink; see docs/mystic_auth/error-monitoring/overview.md). Empty (default) = error monitoring disabled entirely, no SDK call is ever made.
    SENTRY_ENVIRONMENT: str = ""                    # Optional. Tag reported alongside every event (e.g. "production", "staging"). Falls back to ENVIRONMENT if unset.

    # The root .env is shared with docker-compose.yml/docker-compose.prod.yml's
    # `env_file:` directive, which also passes it to infra-only services
    # (e.g. REDIS_PASSWORD for redis-server, BUGSINK_* for the optional
    # monitoring service, see docs/mystic_auth/error-monitoring/overview.md) that
    # have no corresponding Settings field. pydantic-settings defaults to
    # extra="forbid", which only actually bites when Settings' own
    # env_file resolves to a real file, true when running from the repo
    # root (e.g. tests, which need cwd=/repo to import `backend.app...`),
    # not when running the app itself (cwd=/app, where a relative
    # ".env" doesn't resolve to anything, so only explicitly-declared
    # fields are ever read from the process environment either way).
    # "ignore" makes both paths behave identically instead of a
    # test-only crash on any env var this app doesn't itself declare.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_minimum_strength(cls, value: str) -> str:
        # A short/low-entropy SECRET_KEY would otherwise go undetected until
        # someone forges a token against it; fail fast at startup instead.
        # 32 chars is a floor, not a real entropy guarantee; it only catches
        # placeholder/example values like "changeme" or "secret".
        if len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return value

    @property
    def cors_allowed_origins(self) -> list[str]:
        """
        Every origin CORSMiddleware should allow: FRONTEND_BASE_URL always,
        plus whatever FRONTEND_ADDITIONAL_BASE_URLS supplies. Kept here
        (rather than inline in main.py) so it's unit-testable on its own,
        same rationale as client_ip.py parsing TRUSTED_PROXY_IPS itself
        rather than leaving that to each call site.
        """
        extra = (
            origin.strip()
            for origin in self.FRONTEND_ADDITIONAL_BASE_URLS.split(",")
        )
        # dict.fromkeys, not set(): preserves the (otherwise arbitrary)
        # order origins were configured in, which matters only for reading
        # error messages/logs deterministically, never for CORS semantics
        # itself (allow_origins is checked as an unordered set of matches).
        return list(dict.fromkeys([self.FRONTEND_BASE_URL, *(o for o in extra if o)]))


settings = Settings()
