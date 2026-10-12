from backend.app.core.settings import AppSettings


def test_default_app_policy_names_is_empty_when_unset():
    settings = AppSettings(_env_file=None)

    assert settings.default_app_policy_names == []


def test_default_app_policy_names_parses_deduplicates_and_trims():
    settings = AppSettings(
        _env_file=None,
        DEFAULT_APP_POLICIES=" billing_admin , support_agent, billing_admin ,",
    )

    assert settings.default_app_policy_names == ["billing_admin", "support_agent"]
