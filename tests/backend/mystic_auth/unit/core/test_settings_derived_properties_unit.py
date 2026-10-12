import pytest

from backend.mystic_auth.core.settings import Settings


@pytest.mark.parametrize(
    ("environment", "expected_secure"),
    [("development", False), ("Development", False), ("production", True), ("staging", True)],
)
def test_secure_cookies_only_disable_for_development(environment, expected_secure):
    settings = Settings.model_construct(ENVIRONMENT=environment)

    assert settings.secure_cookies is expected_secure


@pytest.mark.parametrize(
    ("database_url", "expected_url"),
    [
        (
            "postgresql+asyncpg://user:pass@localhost:5432/db",
            "postgresql://user:pass@localhost:5432/db",
        ),
        ("postgresql://user:pass@localhost:5432/db", "postgresql://user:pass@localhost:5432/db"),
        (
            "postgresql+asyncpg://user:pass@localhost:5432/postgresql+asyncpg://db",
            "postgresql://user:pass@localhost:5432/postgresql+asyncpg://db",
        ),
    ],
)
def test_procrastinate_database_url_rewrites_only_the_sqlalchemy_scheme(database_url, expected_url):
    settings = Settings.model_construct(DATABASE_URL=database_url)

    assert settings.procrastinate_database_url == expected_url
