# tests/backend/mystic_auth/unit/test_settings_unit.py
import pytest
from pydantic import ValidationError

from backend.mystic_auth.core.settings import Settings

# Every Settings field is required, no Python-level defaults, with two
# exceptions (see the dedicated tests below for each): TRUSTED_PROXY_IPS
# defaults to "" since only the backend service needs a real value, while
# alembic and procrastinate_worker read the same env file directly and never
# use it; SESSION_ROW_RETENTION_HOURS defaults to 1 since it's a generic
# internal buffer with no reason to vary by deployment, not a value forks
# need to tune per .env/AGENTS.md's "default a required-but-service-specific
# Settings field instead of padding every env file with it" convention.
# .env.dev (or the process environment) is the single source of truth for every
# other field, in dev and prod alike. This fixture is a complete, valid
# payload; the tests below poke at deviations from it.
_ALL_FIELDS = {
    "BACKEND_BASE_URL": "http://localhost:8000",
    "FRONTEND_BASE_URL": "http://localhost:5173",
    "FRONTEND_ADDITIONAL_BASE_URLS": "",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
    "DB_POOL_SIZE": 10,
    "DB_MAX_OVERFLOW": 20,
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "pass",
    "POSTGRES_DB": "db",
    "SECRET_KEY": "a" * 32,
    "ACCESS_TOKEN_EXPIRE_MINUTES": 15,
    "REFRESH_TOKEN_EXPIRE_MINUTES": 43200,
    "JWT_ALGORITHM": "HS256",
    "JWT_ISSUER": "http://localhost:8000",
    "JWT_AUDIENCE": "http://localhost:8000",
    "RESET_TOKEN_EXPIRE_MINUTES": 60,
    "ACCOUNT_DELETE_TOKEN_EXPIRE_MINUTES": 60,
    "GOOGLE_CLIENT_ID": "client-id",
    "GOOGLE_CLIENT_SECRET": "client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/oauth2/callback/google",
    "VALKEY_URL": "redis://localhost:6379/0",
    "CACHE_DEFAULT_TTL": 300,
    "FROM_EMAIL": "from@example.com",
    "GMAIL_APP_PASSWORD": "app-password",
    "SUPPORT_EMAIL": "",
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": 587,
    "APP_NAME": "TestApp",
    "LOGIN_LOCKOUT_TIME": 300,
    "MAX_FAILED_LOGIN_ATTEMPTS": 5,
    "LOGIN_LOCKOUT_TIME_PER_IP": 300,
    "MAX_FAILED_LOGIN_ATTEMPTS_PER_IP": 20,
    "MAX_REQUESTS_PER_WINDOW": 100,
    "REQUEST_WINDOW_SECONDS": 60,
    "LOG_LEVEL": "INFO",
    "ENVIRONMENT": "development",
    "TRUSTED_PROXY_IPS": "",
    "GEOIP_DB_PATH": "",
    "SENTRY_DSN": "",
    "SENTRY_ENVIRONMENT": "",
    "ACCOUNT_PURGE_GRACE_DAYS": 30,
    "SESSION_ROW_RETENTION_HOURS": 1,
    "REFRESH_TOKEN_REUSE_GRACE_SECONDS": 10,
    "USER_EXPORT_MAX_ROWS": 50000,
}


def test_settings_construction_succeeds_with_only_declared_fields():
    # Baseline: confirms the fixture above is a complete, valid payload.
    # If this fails, every other test in the file is testing against a
    # payload that was already broken for an unrelated reason.
    Settings(_env_file=None, **_ALL_FIELDS)


@pytest.mark.parametrize(
    "missing_field",
    sorted(set(_ALL_FIELDS) - {"TRUSTED_PROXY_IPS", "SESSION_ROW_RETENTION_HOURS", "REFRESH_TOKEN_REUSE_GRACE_SECONDS"}),
)
def test_settings_construction_fails_when_any_field_is_missing(missing_field, monkeypatch):
    # Every field except TRUSTED_PROXY_IPS and SESSION_ROW_RETENTION_HOURS is
    # required: a silent fallback could let a real deployment start up
    # misconfigured with no error.
    # monkeypatch.delenv is needed alongside omitting the kwarg: _env_file=None
    # only disables reading a dotenv file, pydantic-settings still falls back
    # to the real process environment (set here by docker-compose's env_file:),
    # which this suite runs inside.
    monkeypatch.delenv(missing_field, raising=False)
    payload = {key: value for key, value in _ALL_FIELDS.items() if key != missing_field}

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **payload)


def test_trusted_proxy_ips_defaults_to_empty_when_missing(monkeypatch):
    # The one exception to "every field is required": alembic and
    # procrastinate_worker read the same env file as the backend but never
    # call get_client_ip(), so they shouldn't need a value here at all. Only
    # the backend service actually needs a real value, injected via each
    # prod/local-prod-* Compose file's own environment: override.
    monkeypatch.delenv("TRUSTED_PROXY_IPS", raising=False)
    payload = {key: value for key, value in _ALL_FIELDS.items() if key != "TRUSTED_PROXY_IPS"}

    settings = Settings(_env_file=None, **payload)

    assert settings.TRUSTED_PROXY_IPS == ""


def test_session_row_retention_hours_defaults_to_one_when_missing(monkeypatch):
    # The other exception to "every field is required": a generic internal
    # cleanup buffer, not a per-deployment knob, so no env file needs to
    # carry it (see the fixture comment above).
    monkeypatch.delenv("SESSION_ROW_RETENTION_HOURS", raising=False)
    payload = {key: value for key, value in _ALL_FIELDS.items() if key != "SESSION_ROW_RETENTION_HOURS"}

    settings = Settings(_env_file=None, **payload)

    assert settings.SESSION_ROW_RETENTION_HOURS == 1


def test_settings_ignores_env_vars_that_are_not_declared_fields():
    # Regression guard: env/mystic_auth/.env.dev is shared with docker-compose.dev.yml's
    # `env_file:` directive, which also passes it to infra-only services.
    # VALKEY_PASSWORD (valkey-server's own auth) and BUGSINK_* (the optional
    # self-hosted error-monitoring service, see
    # docs/mystic_auth/error-monitoring/overview.md) have no corresponding
    # Settings field. pydantic-settings defaults to extra="forbid", which
    # crashed Settings() construction whenever such a var was present.
    # Settings.Config now sets extra="ignore".
    payload = {
        **_ALL_FIELDS,
        "VALKEY_PASSWORD": "valkey-password",
        "BUGSINK_SECRET_KEY": "bugsink-secret",
        "BUGSINK_SUPERUSER_EMAIL": "admin@example.com",
        "BUGSINK_SUPERUSER_PASSWORD": "bugsink-password",
        "BUGSINK_BASE_URL": "http://localhost:8010",
    }

    settings = Settings(_env_file=None, **payload)

    assert settings.APP_NAME == "TestApp"
    assert not hasattr(settings, "VALKEY_PASSWORD")


# ---------------------------- cors_allowed_origins ----------------------------


def test_cors_allowed_origins_is_just_frontend_base_url_when_additional_unset():
    settings = Settings(_env_file=None, **_ALL_FIELDS)

    assert settings.cors_allowed_origins == ["http://localhost:5173"]


def test_cors_allowed_origins_includes_additional_origins_in_order():
    payload = {
        **_ALL_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": "https://staging.example.com,https://www.example.com",
    }

    settings = Settings(_env_file=None, **payload)

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://staging.example.com",
        "https://www.example.com",
    ]


def test_cors_allowed_origins_ignores_blank_entries_and_stray_whitespace():
    payload = {
        **_ALL_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": " https://staging.example.com , , https://www.example.com ,",
    }

    settings = Settings(_env_file=None, **payload)

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://staging.example.com",
        "https://www.example.com",
    ]


def test_cors_allowed_origins_deduplicates_a_repeated_origin():
    payload = {
        **_ALL_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": "http://localhost:5173,https://www.example.com",
    }

    settings = Settings(_env_file=None, **payload)

    assert settings.cors_allowed_origins == ["http://localhost:5173", "https://www.example.com"]


def test_refresh_token_reuse_grace_seconds_defaults_to_ten_when_missing(monkeypatch):
    monkeypatch.delenv("REFRESH_TOKEN_REUSE_GRACE_SECONDS", raising=False)
    payload = {key: value for key, value in _ALL_FIELDS.items() if key != "REFRESH_TOKEN_REUSE_GRACE_SECONDS"}

    settings = Settings(_env_file=None, **payload)

    assert settings.REFRESH_TOKEN_REUSE_GRACE_SECONDS == 10


def test_secret_key_validation_rejects_short_values():
    with pytest.raises(ValidationError, match="SECRET_KEY must be at least 32 characters"):
        Settings(_env_file=None, **{**_ALL_FIELDS, "SECRET_KEY": "too-short"})
