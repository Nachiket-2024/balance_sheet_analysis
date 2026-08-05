# tests/backend/mystic_auth/unit/redis/test_client_unit.py
#
# redis_client is a module-level singleton built once at import time; this
# guards that it's actually wired to settings.REDIS_URL with
# decode_responses=True (every caller assumes str, not bytes, back from
# Redis), since nothing else in the suite asserts on its construction.
from backend.mystic_auth.core.settings import settings
from backend.mystic_auth.redis.client import redis_client
from redis.asyncio import Redis


def test_redis_client_is_a_redis_instance():
    assert isinstance(redis_client, Redis)


def test_redis_client_decodes_responses_to_str():
    # Every caller (rate_limiter_service, session_service, taskiq broker)
    # treats Redis replies as str; bytes back would break them silently.
    assert redis_client.connection_pool.connection_kwargs["decode_responses"] is True


def test_redis_client_is_configured_from_settings_redis_url():
    pool_kwargs = redis_client.connection_pool.connection_kwargs
    host = pool_kwargs["host"]
    port = pool_kwargs["port"]

    assert f"{host}:{port}" in settings.REDIS_URL
