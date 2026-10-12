# Unit coverage for /health and /health/ready, called directly as plain
# coroutines with DB/Valkey mocked, so both the healthy and failing paths
# are exercised without a real Postgres/Valkey connection.
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.mystic_auth.api.health_routes.health_routes import health, health_ready

MODULE = "backend.mystic_auth.api.health_routes.health_routes"


@pytest.mark.asyncio
async def test_health_returns_ok_with_no_dependency_checks():
    result = await health()
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready_returns_200_when_all_dependencies_are_healthy(mocker):
    db = MagicMock()
    db.execute = AsyncMock(return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.ping", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.settings.GEOIP_DB_PATH", "")

    response = await health_ready(db=db)

    assert response.status_code == 200
    body = json.loads(response.body.decode())
    assert body == {"status": "ok", "checks": {"database": "ok", "valkey": "ok", "geoip": "disabled"}}


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_database_is_down(mocker):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("connection refused"))
    mocker.patch(f"{MODULE}.valkey_client.ping", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.settings.GEOIP_DB_PATH", "")

    response = await health_ready(db=db)

    assert response.status_code == 503
    body = json.loads(response.body.decode())
    assert body == {"status": "error", "checks": {"database": "error", "valkey": "ok", "geoip": "disabled"}}


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_valkey_is_down(mocker):
    db = MagicMock()
    db.execute = AsyncMock(return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.ping", new_callable=AsyncMock, side_effect=RuntimeError("timeout"))
    mocker.patch(f"{MODULE}.settings.GEOIP_DB_PATH", "")

    response = await health_ready(db=db)

    assert response.status_code == 503
    body = json.loads(response.body.decode())
    assert body == {"status": "error", "checks": {"database": "ok", "valkey": "error", "geoip": "disabled"}}


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_configured_geoip_database_is_missing(mocker, tmp_path):
    db = MagicMock()
    db.execute = AsyncMock(return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.ping", new_callable=AsyncMock, return_value=True)
    mocker.patch(f"{MODULE}.settings.GEOIP_DB_PATH", str(tmp_path / "missing.mmdb"))

    response = await health_ready(db=db)

    assert response.status_code == 503
    body = json.loads(response.body.decode())
    assert body["checks"] == {"database": "ok", "valkey": "ok", "geoip": "error"}


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_configured_geoip_database_is_corrupt(mocker, tmp_path):
    db = MagicMock()
    db.execute = AsyncMock(return_value=None)
    mocker.patch(f"{MODULE}.valkey_client.ping", new_callable=AsyncMock, return_value=True)
    corrupt_db = tmp_path / "corrupt.mmdb"
    corrupt_db.write_bytes(b"not a MaxMind database")
    mocker.patch(f"{MODULE}.settings.GEOIP_DB_PATH", str(corrupt_db))

    response = await health_ready(db=db)

    assert response.status_code == 503
    body = json.loads(response.body.decode())
    assert body["checks"] == {"database": "ok", "valkey": "ok", "geoip": "error"}
