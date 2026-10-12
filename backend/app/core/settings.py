"""Application-owned settings for projects built on the MysticAuth template.

Keep downstream configuration here instead of adding fields to the upstream
``mystic_auth.core.settings.Settings`` model. Upstream authentication code
reads the narrow extension property exposed by this module, so an app only
needs to edit this app-owned file and its app-owned env files.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_MODULE_ROOT = Path(__file__).resolve()
# In the repository checkout this file is backend/app/core/settings.py; in the
# image it is /app/app/core/settings.py. Find the first parent that contains
# the shared env directory so native runs and container runs load the same
# development defaults.
_REPO_ROOT = next(
    (parent for parent in (_MODULE_ROOT.parents[2], _MODULE_ROOT.parents[3]) if (parent / "env").is_dir()),
    _MODULE_ROOT.parents[2],
)


class AppSettings(BaseSettings):
    """Configuration owned by the downstream application."""

    DEFAULT_APP_POLICIES: str = ""

    model_config = SettingsConfigDict(
        env_file=(
            _REPO_ROOT / "env" / "mystic_auth" / ".env.dev",
            _REPO_ROOT / "env" / "app" / ".env.dev",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def default_app_policy_names(self) -> list[str]:
        """Return configured policy names, trimmed and deduplicated."""
        names = (name.strip() for name in self.DEFAULT_APP_POLICIES.split(","))
        return list(dict.fromkeys(name for name in names if name))


app_settings = AppSettings()
