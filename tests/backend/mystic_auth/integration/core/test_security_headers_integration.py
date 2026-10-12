# Regression guard: main.py used to register no security-headers middleware,
# so responses had no X-Frame-Options, CSP, HSTS, etc. Tested end-to-end
# against the real app, since a unit test on SecurityHeadersMiddleware alone
# wouldn't catch middleware ordering or registration bugs.
import pytest


@pytest.mark.asyncio
async def test_response_carries_security_hardening_headers(client):
    resp = await client.get("/")

    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


@pytest.mark.asyncio
async def test_hsts_header_present_in_production(client, mocker):
    mocker.patch("backend.mystic_auth.auth.security.security_headers_middleware.settings.ENVIRONMENT", "production")

    resp = await client.get("/")

    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


@pytest.mark.asyncio
async def test_hsts_header_absent_outside_production(client, mocker):
    mocker.patch("backend.mystic_auth.auth.security.security_headers_middleware.settings.ENVIRONMENT", "development")

    resp = await client.get("/")

    assert "Strict-Transport-Security" not in resp.headers


@pytest.mark.asyncio
async def test_docs_page_gets_a_csp_that_allows_its_cdn_assets(client):
    # Regression guard: the strict `default-src 'none'` CSP used elsewhere
    # also blocked Swagger UI's CDN assets and inline init script, so /docs
    # loaded (200) but rendered as a blank page in a real browser.
    resp = await client.get("/docs")

    from backend.mystic_auth.core.settings import settings
    if settings.ENVIRONMENT == "production":
        assert resp.status_code == 404
        return

    assert resp.status_code == 200
    csp = resp.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp


@pytest.mark.asyncio
async def test_redoc_page_gets_a_csp_that_allows_its_cdn_assets(client):
    resp = await client.get("/redoc")

    from backend.mystic_auth.core.settings import settings
    if settings.ENVIRONMENT == "production":
        assert resp.status_code == 404
        return

    assert resp.status_code == 200
    csp = resp.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in csp
    assert "fonts.googleapis.com" in csp


@pytest.mark.asyncio
async def test_ordinary_routes_keep_the_strict_csp_docs_relaxation_does_not_leak(client):
    resp = await client.get("/")

    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"


@pytest.mark.asyncio
async def test_security_headers_present_even_on_error_responses(client):
    # A 404 still passes through the middleware stack; headers should not be
    # skipped just because the request failed.
    resp = await client.get("/no-such-route")

    assert resp.status_code == 404
    assert resp.headers["X-Frame-Options"] == "DENY"


@pytest.mark.asyncio
async def test_security_headers_present_when_trusted_host_rejects_request(client):
    resp = await client.get("/health", headers={"host": "evil.example"})

    assert resp.status_code == 400
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"


@pytest.mark.asyncio
async def test_cors_preflight_allows_only_the_configured_frontend_origin(client):
    from backend.mystic_auth.core.settings import settings

    resp = await client.options(
        "/auth/login",
        headers={
            "Origin": settings.FRONTEND_BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert resp.headers["Access-Control-Allow-Origin"] == settings.FRONTEND_BASE_URL
    assert resp.headers["Access-Control-Allow-Credentials"] == "true"


@pytest.mark.asyncio
async def test_cors_preflight_rejects_an_untrusted_origin(client):
    resp = await client.options(
        "/auth/login",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    # Starlette's CORSMiddleware doesn't reject a disallowed origin with a
    # 4xx; it just omits Access-Control-Allow-Origin, which is what makes
    # the browser block the real request.
    assert "Access-Control-Allow-Origin" not in resp.headers
