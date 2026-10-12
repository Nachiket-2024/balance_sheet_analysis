import traceback

import geoip2.database
import geoip2.errors

from ..core.settings import settings
from ..logging.logging_config import get_logger

logger = get_logger(__name__)

# Lazily constructed, module-level singleton: opening the .mmdb file is a
# one-time cost (it's memory-mapped, not re-read per lookup), so every
# session create/rotate reuses the same open Reader rather than reopening
# the file on every login. None means either GEOIP_DB_PATH is unset
# (feature disabled) or the file failed to open - both logged once here,
# not on every subsequent lookup.
_reader: geoip2.database.Reader | None = None
_reader_load_attempted = False


def _get_reader() -> geoip2.database.Reader | None:
    global _reader, _reader_load_attempted
    if _reader_load_attempted:
        return _reader

    _reader_load_attempted = True
    if not settings.GEOIP_DB_PATH:
        return None

    try:
        _reader = geoip2.database.Reader(settings.GEOIP_DB_PATH)
    except Exception:
        logger.error(
            "Failed to open GeoLite2 database at GEOIP_DB_PATH=%r; "
            "Manage Sessions' Location column will show \"Unknown\" until this is fixed:\n%s",
            settings.GEOIP_DB_PATH,
            traceback.format_exc(),
        )
        _reader = None

    return _reader


def resolve_city_country(ip: str | None) -> tuple[str | None, str | None]:
    """
    Best-effort city/country resolution for a login IP, used only for
    display on the Manage Sessions dashboard card. Never raises: an
    unset/missing database, a private/reserved/malformed address, or any
    other lookup failure all just yield (None, None), the same
    fail-open-and-log-nothing-louder-than-a-warning posture as every other
    best-effort field on UserSession (see session_service.py).
    """
    if not ip:
        return None, None

    reader = _get_reader()
    if reader is None:
        return None, None

    try:
        response = reader.city(ip)
    except geoip2.errors.AddressNotFoundError:
        return None, None
    except Exception:
        logger.warning("GeoIP lookup failed for ip=%r:\n%s", ip, traceback.format_exc())
        return None, None

    return response.city.name, response.country.name
