from backend.mystic_auth.core.secret_provider import (
    EnvironmentSecretProvider,
    require_secret,
)


def test_environment_provider_returns_named_secret():
    provider = EnvironmentSecretProvider({"APP_WEBHOOK_SECRET": "value"})

    assert provider.get_secret("APP_WEBHOOK_SECRET") == "value"


def test_environment_provider_rejects_invalid_name():
    provider = EnvironmentSecretProvider({"not-valid": "value"})

    try:
        provider.get_secret("not-valid")
    except ValueError as exc:
        assert str(exc) == "Secret names must be non-empty environment identifiers"
    else:
        raise AssertionError("Expected invalid secret name to raise ValueError")


def test_require_secret_rejects_missing_secret():
    provider = EnvironmentSecretProvider({})

    try:
        require_secret(provider, "APP_WEBHOOK_SECRET")
    except RuntimeError as exc:
        assert str(exc) == "Required integration secret 'APP_WEBHOOK_SECRET' is not configured"
    else:
        raise AssertionError("Expected missing secret to raise RuntimeError")
