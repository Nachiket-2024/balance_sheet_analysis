import asyncio
from pathlib import Path

import geoip2.database
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.settings import settings
from ...database.connection import database
from ...logging.logging_config import get_logger
from ...valkey.client import valkey_client

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


def _geoip_database_available(path: str) -> bool:
    geoip_path = Path(path)
    if not geoip_path.is_file() or geoip_path.stat().st_size == 0:
        return False
    reader = geoip2.database.Reader(str(geoip_path))
    try:
        # Opening the file alone isn't enough: a truncated or corrupt mmdb
        # can exist and be non-empty while every real lookup fails.
        reader.metadata()
        return True
    finally:
        reader.close()


@router.get("/health")
async def health():
    """
    Liveness probe: is the process up and able to serve requests at all.
    Deliberately cheap (no dependency checks) so it's safe to poll frequently.
    Use /health/ready for an actual dependency-aware readiness check.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(database.get_session)):
    """
    Readiness probe: confirms Postgres and Valkey connectivity. Each check is
    wrapped in its own try/except, so one dependency being down still
    reports the other's real status instead of masking it.
    """
    checks: dict[str, str] = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.error("Readiness check: database connectivity failed", exc_info=True)
        checks["database"] = "error"

    try:
        await valkey_client.ping()
        checks["valkey"] = "ok"
    except Exception:
        logger.error("Readiness check: valkey connectivity failed", exc_info=True)
        checks["valkey"] = "error"

    # An explicitly configured GeoIP database is a runtime dependency for
    # session-location capture. Do not advertise readiness while the updater
    # has failed or the mounted database is empty.
    if settings.GEOIP_DB_PATH:
        try:
            if not await asyncio.to_thread(_geoip_database_available, settings.GEOIP_DB_PATH):
                raise FileNotFoundError(settings.GEOIP_DB_PATH)
            checks["geoip"] = "ok"
        except Exception:
            logger.error("Readiness check: GeoIP database is unavailable", exc_info=True)
            checks["geoip"] = "error"
    else:
        checks["geoip"] = "disabled"

    all_ok = all(status in {"ok", "disabled"} for status in checks.values())
    return JSONResponse(
        content={"status": "ok" if all_ok else "error", "checks": checks},
        status_code=200 if all_ok else 503,
    )
