# tests/backend/mystic_auth/unit/test_settings_unit.py
from backend.mystic_auth.core.settings import Settings

_REQUIRED_FIELDS = {
    "BACKEND_BASE_URL": "http://localhost:8000",
    "FRONTEND_BASE_URL": "http://localhost:5173",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "pass",
    "POSTGRES_DB": "db",
    "SECRET_KEY": "a" * 32,
    "ACCESS_TOKEN_EXPIRE_MINUTES": 15,
    "REFRESH_TOKEN_EXPIRE_MINUTES": 43200,
    "JWT_ALGORITHM": "HS256",
    "RESET_TOKEN_EXPIRE_MINUTES": 60,
    "GOOGLE_CLIENT_ID": "client-id",
    "GOOGLE_CLIENT_SECRET": "client-secret",
    "GOOGLE_REDIRECT_URI": "http://localhost:8000/auth/oauth2/callback/google",
    "REDIS_URL": "redis://localhost:6379/0",
    "CACHE_DEFAULT_TTL": 300,
    "FROM_EMAIL": "from@example.com",
    "GMAIL_APP_PASSWORD": "app-password",
    "APP_NAME": "TestApp",
    "LOGIN_LOCKOUT_TIME": 300,
    "MAX_FAILED_LOGIN_ATTEMPTS": 5,
    "LOGIN_LOCKOUT_TIME_PER_IP": 300,
    "MAX_FAILED_LOGIN_ATTEMPTS_PER_IP": 20,
    "MAX_REQUESTS_PER_WINDOW": 100,
    "REQUEST_WINDOW_SECONDS": 60,
}


def test_settings_construction_succeeds_with_only_declared_fields():
    # Baseline: the fixture above actually is a complete, valid Settings
    # payload : if this ever fails, the extra-field regression guards below
    # would be testing against a payload that was already broken for an
    # unrelated reason.
    Settings(**_REQUIRED_FIELDS)


def test_settings_ignores_env_vars_that_are_not_declared_fields():
    # Regression guard: the root .env is shared with docker-compose.yml's
    # `env_file:` directive, which also passes it to infra-only services :
    # REDIS_PASSWORD (redis-server's own auth) and BUGSINK_* (the optional
    # self-hosted error-monitoring service, see
    # docs/mystic_auth/error-monitoring/overview.md) have no corresponding Settings
    # field. pydantic-settings defaults to extra="forbid", which crashed
    # Settings() construction the moment any such var was present : this
    # only actually surfaced when Settings' own env_file resolved to a real
    # file (true when cwd=/repo, e.g. running tests) rather than the app's
    # own cwd=/app, where a relative ".env" never resolves to anything :
    # so the same .env silently worked for the running app while crashing
    # every test collection. Settings.Config now sets extra="ignore".
    payload = {
        **_REQUIRED_FIELDS,
        "REDIS_PASSWORD": "redis-password",
        "BUGSINK_SECRET_KEY": "bugsink-secret",
        "BUGSINK_SUPERUSER_EMAIL": "admin@example.com",
        "BUGSINK_SUPERUSER_PASSWORD": "bugsink-password",
        "BUGSINK_BASE_URL": "http://localhost:8010",
    }

    settings = Settings(**payload)

    assert settings.APP_NAME == "TestApp"
    assert not hasattr(settings, "REDIS_PASSWORD")


# ---------------------------- optional field defaults ----------------------------

_OPTIONAL_FIELDS = (
    "SUPPORT_EMAIL",
    "SMTP_HOST",
    "SMTP_PORT",
    "LOG_LEVEL",
    "ENVIRONMENT",
    "TRUSTED_PROXY_IPS",
    "FRONTEND_ADDITIONAL_BASE_URLS",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
)


def test_optional_fields_default_when_unset(monkeypatch):
    # These fields are all optional so existing .env files/CI configs that
    # predate them keep working unchanged : verify the defaults actually
    # match what main.py/client_ip.py/sentry_service.py assume when unset.
    # The real repo-root .env (loaded by Settings.Config.env_file, and also
    # passed into this process's environment by docker-compose) sets several
    # of these, so it must be cleared from both places for this test to
    # actually observe the field defaults rather than the real deployment's
    # config.
    for field in _OPTIONAL_FIELDS:
        monkeypatch.delenv(field, raising=False)

    settings = Settings(_env_file=None, **_REQUIRED_FIELDS)

    assert settings.SUPPORT_EMAIL == ""
    assert settings.SMTP_HOST == "smtp.gmail.com"
    assert settings.SMTP_PORT == 587
    assert settings.LOG_LEVEL == "INFO"
    assert settings.ENVIRONMENT == "development"
    assert settings.TRUSTED_PROXY_IPS == ""
    assert settings.FRONTEND_ADDITIONAL_BASE_URLS == ""
    assert settings.SENTRY_DSN == ""
    assert settings.SENTRY_ENVIRONMENT == ""


def test_optional_fields_can_be_overridden():
    payload = {
        **_REQUIRED_FIELDS,
        "SUPPORT_EMAIL": "support@example.com",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": 2525,
        "LOG_LEVEL": "DEBUG",
        "ENVIRONMENT": "production",
        "TRUSTED_PROXY_IPS": "10.0.0.1,10.0.0.2",
        "FRONTEND_ADDITIONAL_BASE_URLS": "https://staging.example.com,https://www.example.com",
        "SENTRY_DSN": "https://public@sentry.example.com/1",
        "SENTRY_ENVIRONMENT": "staging",
    }

    settings = Settings(**payload)

    assert settings.SUPPORT_EMAIL == "support@example.com"
    assert settings.SMTP_HOST == "smtp.example.com"
    assert settings.SMTP_PORT == 2525
    assert settings.LOG_LEVEL == "DEBUG"
    assert settings.ENVIRONMENT == "production"
    assert settings.TRUSTED_PROXY_IPS == "10.0.0.1,10.0.0.2"
    assert settings.FRONTEND_ADDITIONAL_BASE_URLS == "https://staging.example.com,https://www.example.com"
    assert settings.SENTRY_DSN == "https://public@sentry.example.com/1"
    assert settings.SENTRY_ENVIRONMENT == "staging"


# ---------------------------- cors_allowed_origins ----------------------------


def test_cors_allowed_origins_is_just_frontend_base_url_when_additional_unset():
    settings = Settings(**_REQUIRED_FIELDS)

    assert settings.cors_allowed_origins == ["http://localhost:5173"]


def test_cors_allowed_origins_includes_additional_origins_in_order():
    payload = {
        **_REQUIRED_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": "https://staging.example.com,https://www.example.com",
    }

    settings = Settings(**payload)

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://staging.example.com",
        "https://www.example.com",
    ]


def test_cors_allowed_origins_ignores_blank_entries_and_stray_whitespace():
    payload = {
        **_REQUIRED_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": " https://staging.example.com , , https://www.example.com ,",
    }

    settings = Settings(**payload)

    assert settings.cors_allowed_origins == [
        "http://localhost:5173",
        "https://staging.example.com",
        "https://www.example.com",
    ]


def test_cors_allowed_origins_deduplicates_a_repeated_origin():
    payload = {
        **_REQUIRED_FIELDS,
        "FRONTEND_ADDITIONAL_BASE_URLS": "http://localhost:5173,https://www.example.com",
    }

    settings = Settings(**payload)

    assert settings.cors_allowed_origins == ["http://localhost:5173", "https://www.example.com"]
