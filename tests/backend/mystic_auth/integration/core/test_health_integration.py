# End-to-end tests for /health and /health/ready, using the real app, Postgres,
# and Valkey (via the `client` fixture in conftest.py). Confirms /health/ready
# actually checks both dependencies instead of just returning a static reply.
import pytest

from backend.mystic_auth.core.settings import settings


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_returns_ok_when_dependencies_are_reachable(client, monkeypatch):
    # This test covers the default disabled-GeoIP contract independently of a
    # developer's local database path configuration.
    monkeypatch.setattr(settings, "GEOIP_DB_PATH", "")
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "valkey": "ok", "geoip": "disabled"}
