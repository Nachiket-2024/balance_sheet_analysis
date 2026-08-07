# tests/backend/mystic_auth/integration/test_health_integration.py
#
# End-to-end coverage for /health and /health/ready against the real ASGI
# app, real PostgreSQL, and real Redis (via the shared `client` fixture :
# see conftest.py). Confirms the readiness endpoint actually reaches both
# dependencies rather than just returning a static response.
import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_returns_ok_when_dependencies_are_reachable(client):
    resp = await client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}
