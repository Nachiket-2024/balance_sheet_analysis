# tests/backend/app/llm/test_llm_service_unit.py
#
# Pure unit coverage for llm_service.ask_groq's error handling. No HTTP
# client, no DB; httpx itself is mocked so these run instantly and never
# touch the real Groq API.
from unittest.mock import AsyncMock, MagicMock

import pytest
from backend.app.llm import llm_service

MODULE = "backend.app.llm.llm_service"


def _mock_client(mocker, response=None, raise_exc=None):
    mock_client = MagicMock()
    if raise_exc is not None:
        mock_client.post = AsyncMock(side_effect=raise_exc)
    else:
        mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mocker.patch(f"{MODULE}.httpx.AsyncClient", return_value=mock_client)


@pytest.mark.asyncio
async def test_raises_when_api_key_not_configured(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "")

    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not configured"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_returns_content_on_success(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "  the answer  "}}]}
    _mock_client(mocker, response=response)

    answer = await llm_service.ask_groq("question", "context")

    assert answer == "the answer"


@pytest.mark.asyncio
async def test_raises_on_non_200_response(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=500, text="internal error")
    _mock_client(mocker, response=response)

    with pytest.raises(RuntimeError, match="Groq API error"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_raises_on_unexpected_response_shape(mocker):
    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    response = MagicMock(status_code=200, text="{}")
    response.json.return_value = {}
    _mock_client(mocker, response=response)

    with pytest.raises(RuntimeError, match="Unexpected Groq API response shape"):
        await llm_service.ask_groq("question", "context")


@pytest.mark.asyncio
async def test_raises_on_network_failure(mocker):
    import httpx

    mocker.patch(f"{MODULE}.GROQ_API_KEY", "fake-key")
    _mock_client(mocker, raise_exc=httpx.ConnectError("connection refused"))

    with pytest.raises(RuntimeError, match="Failed to reach Groq API"):
        await llm_service.ask_groq("question", "context")
