from pathlib import Path
from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute, not relative to whatever the process's CWD happens to be (a
# relative path here breaks the moment something runs alembic/pytest with
# cwd=backend/ instead of the repo root).
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env."""

    BACKEND_BASE_URL: str                           # Used to build auth redirect URLs back from the frontend
    FRONTEND_BASE_URL: str                          # Primary frontend origin: used for redirect/email links (OAuth callback, verification, password reset) and always CORS-allowed
    FRONTEND_ADDITIONAL_BASE_URLS: str              # Optional comma-separated extra CORS-allowed origins (e.g. staging alongside prod). Empty = none. Never used for redirect/email links; those always point at FRONTEND_BASE_URL

    DATABASE_URL: str                               # Async PostgreSQL URL. Used by Alembic (needs DDL rights) and Procrastinate's queue connector. The app itself prefers APP_DATABASE_URL when set
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    APP_DATABASE_URL: str = ""                      # Optional least-privilege DB URL (CRUD only, no DDL) for the request-serving app and background jobs. Empty (default) falls back to DATABASE_URL

    DB_POOL_SIZE: int                               # Per-process SQLAlchemy pool size. UVICORN_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW) must stay under Postgres max_connections - see docs/mystic_auth/deployment/environment.md
    DB_MAX_OVERFLOW: int                            # Extra connections opened beyond DB_POOL_SIZE under burst load, closed again once idle

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    JWT_ALGORITHM: str
    JWT_ISSUER: str                                 # "iss" claim on every JWT; distinguishes this deployment's tokens from others sharing SECRET_KEY. Typically BACKEND_BASE_URL
    JWT_AUDIENCE: str                                # "aud" claim on every JWT; the token's intended consumer. Typically BACKEND_BASE_URL too, since this API issues and validates its own tokens
    RESET_TOKEN_EXPIRE_MINUTES: int
    ACCOUNT_DELETE_TOKEN_EXPIRE_MINUTES: int        # OAuth-only self-service account-deletion confirmation link lifetime, in minutes

    GOOGLE_CLIENT_ID: str                           # OAuth2 credentials for Google login
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    VALKEY_URL: str
    CACHE_DEFAULT_TTL: int                          # Default TTL for Valkey cache keys, in seconds

    FROM_EMAIL: str                                 # Sender address for verification/password-reset emails
    GMAIL_APP_PASSWORD: str                         # Gmail App password for the FROM_EMAIL account
    SUPPORT_EMAIL: str                              # Reply-to/contact address in email footers. Empty falls back to FROM_EMAIL

    SMTP_HOST: str                                  # SMTP server host (e.g. smtp.gmail.com)
    SMTP_PORT: int                                  # SMTP server port (587 = STARTTLS, Gmail's default)

    EMAIL_ENABLED: bool = True                      # False sends every email through NullEmailSender (logs it, opens no SMTP connection) instead of the real SMTPEmailSender. Useful for local dev/test so signup/reset flows don't burn a real provider's send quota; tests always force this False regardless of .env

    APP_NAME: str                                    # Product name shown in email branding and API responses

    LOGIN_LOCKOUT_TIME: int                         # Lockout duration after failed login attempts, in seconds
    MAX_FAILED_LOGIN_ATTEMPTS: int
    LOGIN_LOCKOUT_TIME_PER_IP: int                  # Lockout duration for an IP after too many failed logins across accounts
    MAX_FAILED_LOGIN_ATTEMPTS_PER_IP: int           # Failed attempts from one IP, across any accounts, before that IP is locked out
    ACTION_RESERVATION_TIME: int = 60               # Valkey reservation lifetime for concurrent one-time auth actions, in seconds
    MAX_REQUESTS_PER_WINDOW: int                    # Rate limit: max requests per window
    REQUEST_WINDOW_SECONDS: int                     # Rate limit window size, in seconds

    LOG_LEVEL: str                                  # Application log level (e.g. INFO)

    ENVIRONMENT: str                                # "development" or "production"; gates docs/redoc exposure in main.py

    TRUSTED_PROXY_IPS: str = ""                     # Comma-separated reverse proxy IPs to trust X-Forwarded-For from. Empty = never trust it, use request.client.host as-is. Only the backend service uses this; defaulted so alembic/procrastinate_worker don't need it in their env file

    GEOIP_DB_PATH: str                              # Path to a local MaxMind GeoLite2-City .mmdb file, used to resolve login IPs to city/country for Manage Sessions' Location column. Empty = geolocation disabled, Location shows "Unknown". Requires a free MaxMind account and license key; the file can't ship in this repo (MaxMind's license forbids redistribution)

    SENTRY_DSN: str                                 # Optional Sentry-protocol DSN (Sentry itself, or a compatible self-hosted server like Bugsink). Empty = error monitoring disabled, no SDK call is made
    SENTRY_ENVIRONMENT: str                         # Optional tag reported with every event (e.g. "production", "staging"). Empty falls back to ENVIRONMENT
    SECURITY_ALERT_WEBHOOK_URL: str = ""            # Optional incident/webhook endpoint for high-signal security alerts
    SECURITY_ALERT_WEBHOOK_TOKEN: str = ""          # Optional bearer token for SECURITY_ALERT_WEBHOOK_URL; never logged
    SECURITY_ALERT_WEBHOOK_TIMEOUT_SECONDS: float = 2.0  # Short fail-open timeout so monitoring cannot block authentication

    ACCOUNT_PURGE_GRACE_DAYS: int                   # Days a soft-deleted account is kept before the daily purge job hard-deletes it
    AUDIT_LOG_RETENTION_DAYS: int = 400              # Rows in security_audit_log/authorization_audit_log older than this get their email/IP/user-agent stripped (not deleted) by the daily retention job, independent of whether the account was ever purged. ~13 months: covers a yearly security review with room to spare; shorten if that's more PII retention than your deployment needs

    # Comma-separated dotted module paths imported by the Procrastinate app
    # before workers start. Downstream projects use this to register their
    # own tasks and worker hooks without editing template task files.
    PROCRASTINATE_TASK_IMPORT_PATHS: str = ""
    PROCRASTINATE_WORKER_MIDDLEWARE_PATHS: str = ""

    REFRESH_TOKEN_REUSE_GRACE_SECONDS: int = 10     # A same-IP retry within this many seconds is rejected without revoking the first request's chain. 0 disables. Defaulted, not in .env*
    SESSION_ROW_RETENTION_HOURS: int = 1           # Hours past expires_at a user_sessions row is kept before the daily sweep (session_cleanup_tasks.py) hard-deletes it. Buffer, not a deployment knob (defaulted, not in .env*): revoked sessions delete immediately on revoke, this only covers ones that lapsed without an explicit revoke
    SESSION_EVENT_MAX_CONNECTIONS_PER_ACCOUNT: int = 5  # Maximum concurrent authenticated SSE streams for one account, enforced globally through Valkey
    SESSION_EVENT_MAX_CONNECTIONS_PER_IP: int = 20      # Maximum concurrent authenticated SSE streams for one client IP, enforced globally through Valkey
    SESSION_EVENT_LEASE_GRACE_SECONDS: int = 30         # Expiry cushion if a worker dies before its SSE cleanup runs

    USER_EXPORT_MAX_ROWS: int                       # Hard ceiling on GET /users/export's row count (that endpoint has no offset/limit). A request matching more rows is rejected instead of loaded into memory in one query

    # For running the backend locally instead of in Docker (Docker itself
    # injects these via docker-compose's --env-file, not this fallback).
    # Both files are read in order so an env/app/ value wins on overlap,
    # matching every docker-compose invocation in this template's own
    # scripts (see docs/mystic_auth/template-usage/ownership-split.md).
    # Also picks up infra-only vars (VALKEY_PASSWORD, BUGSINK_*, etc.) that
    # have no matching Settings field below; extra="ignore" lets those pass
    # through instead of pydantic rejecting them as undeclared.
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / "env" / "mystic_auth" / ".env.dev", _REPO_ROOT / "env" / "app" / ".env.dev"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_key_minimum_strength(cls, value: str) -> str:
        # Fail fast at startup rather than let a weak SECRET_KEY go
        # unnoticed until someone forges a token. 32 chars is just a floor
        # to catch placeholders like "changeme", not a real entropy check.
        if len(value) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return value

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Every origin CORSMiddleware should allow: FRONTEND_BASE_URL plus
        whatever FRONTEND_ADDITIONAL_BASE_URLS adds."""
        extra = (
            origin.strip()
            for origin in self.FRONTEND_ADDITIONAL_BASE_URLS.split(",")
        )
        # dict.fromkeys, not set(): keeps a deterministic order for logging;
        # CORS matching itself doesn't care about order.
        return list(dict.fromkeys([self.FRONTEND_BASE_URL, *(o for o in extra if o)]))

    @property
    def trusted_hosts(self) -> list[str]:
        """Hostnames (no scheme/port) TrustedHostMiddleware should accept on
        the Host header. Reset/verify links are already built from
        FRONTEND_BASE_URL alone, never from the request (see
        account_verification_service.py), so this isn't what keeps those
        links honest - it closes the separate gap that nothing at the app
        layer itself rejects a spoofed Host, which previously meant a
        request straight to the backend's own localhost-only port (bypassing
        nginx/the tunnel, both of which enforce their own Host expectations)
        was accepted with no app-level check at all.

        Derived from cors_allowed_origins' hostnames, since nginx forwards
        the original client Host unchanged (`proxy_set_header Host $host`
        in nginx.frontend.conf), so real traffic's Host always matches one
        of those. "localhost"/"127.0.0.1" are always included too: every
        compose mode's backend healthcheck runs
        `curl http://localhost:8000/health/ready` from inside the
        container, and local direct-port debugging (documented in each
        local-prod compose file) hits the backend the same way.
        TrustedHostMiddleware compares only the hostname, so "localhost:8000"
        already matches a bare "localhost" entry; the port needs no separate
        listing.
        """
        hosts = {urlsplit(origin).hostname for origin in self.cors_allowed_origins}
        # The API may be hosted on a separate origin from the frontend. CORS
        # origins describe browser callers, not every valid Host header the
        # backend itself must serve.
        hosts.add(urlsplit(self.BACKEND_BASE_URL).hostname)
        hosts.update({"localhost", "127.0.0.1"})
        # httpx/Starlette's AsyncClient(transport=ASGITransport(...)) test
        # harness defaults to this exact hostname (see tests/backend/
        # conftest.py's `client` fixture) - the same convention Django's own
        # ALLOWED_HOSTS ships by default, for the same reason: nothing on
        # the real internet resolves "testserver", so allowing it here never
        # widens what a real request can spoof.
        hosts.add("testserver")
        return sorted(h for h in hosts if h)

    @property
    def secure_cookies(self) -> bool:
        """Use Secure cookies everywhere except the plain-HTTP dev stack."""
        return self.ENVIRONMENT.lower() != "development"

    @property
    def procrastinate_database_url(self) -> str:
        """DATABASE_URL rewritten from SQLAlchemy's `postgresql+asyncpg://`
        prefix to the plain `postgresql://` DSN Procrastinate's
        PsycopgConnector expects. Procrastinate opens its own psycopg
        connection pool, separate from the SQLAlchemy engine."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

settings = Settings()
