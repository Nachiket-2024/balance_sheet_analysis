# tests/backend/mystic_auth/unit/valkey/test_valkey_client_unit.py
#
# valkey_client is a module-level singleton built once at import time; this
# guards that it's actually wired to settings.VALKEY_URL with
# decode_responses=True (every caller assumes str, not bytes, back from
# Valkey), since nothing else in the suite asserts on its construction.
from valkey.asyncio import Valkey

from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.valkey.client import (
    VALKEY_SOCKET_TIMEOUT_SECONDS,
    valkey_client,
)


def test_valkey_client_is_a_valkey_instance():
    assert isinstance(valkey_client, Valkey)


def test_valkey_client_decodes_responses_to_str():
    # Every caller (rate_limiter_service, session_service) treats Valkey
    # replies as str; bytes back would break them silently.
    assert valkey_client.connection_pool.connection_kwargs["decode_responses"] is True


def test_valkey_client_is_configured_from_settings_valkey_url():
    pool_kwargs = valkey_client.connection_pool.connection_kwargs
    host = pool_kwargs["host"]
    port = pool_kwargs["port"]

    assert f"{host}:{port}" in settings.VALKEY_URL


def test_valkey_client_has_bounded_socket_timeouts():
    pool_kwargs = valkey_client.connection_pool.connection_kwargs

    assert pool_kwargs["socket_connect_timeout"] == VALKEY_SOCKET_TIMEOUT_SECONDS
    assert pool_kwargs["socket_timeout"] == VALKEY_SOCKET_TIMEOUT_SECONDS
