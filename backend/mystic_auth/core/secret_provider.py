"""Secret-provider boundary for downstream applications.

Mystic Auth does not persist product integration credentials. Downstream
projects inject a provider backed by their deployment's secret manager and
read values only at the point of use.
"""
import os
from collections.abc import Mapping
from typing import Protocol


class SecretProvider(Protocol):
    """Minimal provider contract for integration secrets."""

    def get_secret(self, name: str) -> str | None:
        """Return a secret or ``None`` when the configured name is absent."""


class EnvironmentSecretProvider:
    """Development and simple-deployment provider using injected env vars.

    The environment must be populated by the deployment secret manager or
    Compose secret mechanism. This class never serializes, logs, or returns a
    mapping of all configured secrets.
    """

    def __init__(self, environ: Mapping[str, str] | None = None):
        self._environ = environ if environ is not None else os.environ

    def get_secret(self, name: str) -> str | None:
        if not name or not name.isidentifier():
            raise ValueError("Secret names must be non-empty environment identifiers")
        return self._environ.get(name)


def require_secret(provider: SecretProvider, name: str) -> str:
    """Read one secret and fail clearly when deployment configuration is missing."""
    value = provider.get_secret(name)
    if not value:
        raise RuntimeError(f"Required integration secret {name!r} is not configured")
    return value
