"""Fail-open and cache behavior for optional GeoIP session enrichment."""

from types import SimpleNamespace

import geoip2.errors
import pytest

from backend.mystic_auth.user_session import session_geolocation as module


@pytest.fixture(autouse=True)
def reset_reader_state():
    module._reader = None
    module._reader_load_attempted = False
    yield
    module._reader = None
    module._reader_load_attempted = False


def test_empty_ip_is_not_looked_up(mocker):
    reader = mocker.patch.object(module.geoip2.database, "Reader")

    assert module.resolve_city_country(None) == (None, None)
    assert module.resolve_city_country("") == (None, None)
    reader.assert_not_called()


def test_disabled_database_fails_open_without_opening_reader(mocker):
    mocker.patch.object(module.settings, "GEOIP_DB_PATH", None)
    reader = mocker.patch.object(module.geoip2.database, "Reader")

    assert module.resolve_city_country("203.0.113.10") == (None, None)
    assert module.resolve_city_country("203.0.113.11") == (None, None)
    reader.assert_not_called()


def test_successful_lookup_is_cached_and_returns_city_and_country(mocker):
    mocker.patch.object(module.settings, "GEOIP_DB_PATH", "/geo/GeoLite2-City.mmdb")
    response = SimpleNamespace(
        city=SimpleNamespace(name="Sydney"),
        country=SimpleNamespace(name="Australia"),
    )
    reader = mocker.patch.object(module.geoip2.database, "Reader")
    reader.return_value.city.return_value = response

    assert module.resolve_city_country("198.51.100.10") == ("Sydney", "Australia")
    assert module.resolve_city_country("198.51.100.11") == ("Sydney", "Australia")
    reader.assert_called_once_with("/geo/GeoLite2-City.mmdb")
    assert reader.return_value.city.call_count == 2


def test_missing_address_returns_unknown_without_warning(mocker):
    mocker.patch.object(module.settings, "GEOIP_DB_PATH", "/geo/city.mmdb")
    reader = mocker.patch.object(module.geoip2.database, "Reader")
    reader.return_value.city.side_effect = geoip2.errors.AddressNotFoundError("private address")
    warning = mocker.patch.object(module.logger, "warning")

    assert module.resolve_city_country("192.0.2.1") == (None, None)
    warning.assert_not_called()


def test_unexpected_lookup_error_is_logged_and_fails_open(mocker):
    mocker.patch.object(module.settings, "GEOIP_DB_PATH", "/geo/city.mmdb")
    reader = mocker.patch.object(module.geoip2.database, "Reader")
    reader.return_value.city.side_effect = RuntimeError("corrupt database")
    warning = mocker.patch.object(module.logger, "warning")

    assert module.resolve_city_country("198.51.100.10") == (None, None)
    warning.assert_called_once()


def test_reader_open_error_is_logged_once_and_cached_as_disabled(mocker):
    mocker.patch.object(module.settings, "GEOIP_DB_PATH", "/geo/missing.mmdb")
    reader = mocker.patch.object(module.geoip2.database, "Reader", side_effect=OSError("missing"))
    error = mocker.patch.object(module.logger, "error")

    assert module.resolve_city_country("198.51.100.10") == (None, None)
    assert module.resolve_city_country("198.51.100.11") == (None, None)
    reader.assert_called_once_with("/geo/missing.mmdb")
    error.assert_called_once()
