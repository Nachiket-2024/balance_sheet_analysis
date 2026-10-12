from backend.mystic_auth.core.settings import Settings


def test_trusted_hosts_include_a_separate_backend_origin():
    settings = Settings.model_construct(
        BACKEND_BASE_URL="https://api.example.test",
        FRONTEND_BASE_URL="https://app.example.test",
        FRONTEND_ADDITIONAL_BASE_URLS="https://admin.example.test",
    )

    assert settings.trusted_hosts == [
        "127.0.0.1",
        "admin.example.test",
        "api.example.test",
        "app.example.test",
        "localhost",
        "testserver",
    ]


def test_cors_origins_trim_empty_values_and_deduplicate_in_order():
    settings = Settings.model_construct(
        FRONTEND_BASE_URL="https://app.example.test",
        FRONTEND_ADDITIONAL_BASE_URLS=" https://staging.example.test, ,https://app.example.test,https://preview.example.test ",
    )

    assert settings.cors_allowed_origins == [
        "https://app.example.test",
        "https://staging.example.test",
        "https://preview.example.test",
    ]


def test_trusted_hosts_include_backend_and_additional_origin_hosts():
    settings = Settings.model_construct(
        BACKEND_BASE_URL="https://api.example.test:8443",
        FRONTEND_BASE_URL="https://app.example.test",
        FRONTEND_ADDITIONAL_BASE_URLS="https://staging.example.test",
    )

    assert settings.trusted_hosts == [
        "127.0.0.1",
        "api.example.test",
        "app.example.test",
        "localhost",
        "staging.example.test",
        "testserver",
    ]
