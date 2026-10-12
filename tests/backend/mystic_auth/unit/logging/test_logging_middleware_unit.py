import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.mystic_auth.logging.logging_middleware import LoggingMiddleware

MODULE = "backend.mystic_auth.logging.logging_middleware"


@pytest.mark.asyncio
async def test_logging_middleware_does_not_log_query_string_values(mocker):
    info_mock = mocker.patch(f"{MODULE}.logger.info")
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/oauth/callback")
    async def callback():
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as client:
        response = await client.get("/oauth/callback?code=secret-code&state=secret-state")

    assert response.status_code == 200
    logged_text = " ".join(str(call) for call in info_mock.call_args_list)
    assert "/oauth/callback" in logged_text
    assert "secret-code" not in logged_text
    assert "secret-state" not in logged_text
    assert "?" not in logged_text

    response_call = info_mock.call_args_list[-1]
    assert response_call.args == ("Response",)
    assert response_call.kwargs["extra"]["http_method"] == "GET"
    assert response_call.kwargs["extra"]["http_path"] == "/oauth/callback"
    assert response_call.kwargs["extra"]["http_status"] == 200
    assert isinstance(response_call.kwargs["extra"]["duration_ms"], float)
