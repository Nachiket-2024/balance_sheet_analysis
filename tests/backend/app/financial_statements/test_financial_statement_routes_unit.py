from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.api.financial_statement_routes import (
    financial_statement_routes as routes,
)
from backend.app.balance_sheets.balance_sheet_crud import YFinanceFetchError


async def passthrough(value, *_args, **_kwargs):
    return await value if hasattr(value, "__await__") else value


async def missing(value, *_args, **_kwargs):
    await value if hasattr(value, "__await__") else value
    raise HTTPException(status_code=404, detail="missing")


@pytest.mark.asyncio
async def test_list_and_analyze_financial_statements_authorize_company(mocker):
    user, db = {"email": "analyst@example.com"}, object()
    company = SimpleNamespace(id=4, ticker="EXAMPLE", group_root_id=None)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=passthrough)
    auth = mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    listed = mocker.patch.object(routes, "list_statements", new_callable=AsyncMock, return_value=["row"])

    result = await routes.list_company_financial_statements(4, "income", "quarterly", user, db)
    assert result == ["row"]
    listed.assert_awaited_once_with(4, "income", db, period_type="quarterly")
    assert auth.await_args.args[1] == "balance_sheet:read"

    analysis = {"income": []}
    mocker.patch.object(routes, "calculate_statement_analysis", return_value=analysis)
    assert await routes.analyze_company_financial_statements(4, user, db) == analysis
    assert listed.await_count == 2


@pytest.mark.asyncio
async def test_get_and_import_statement_map_missing_validation_and_provider_errors(mocker):
    user, db = {"email": "analyst@example.com"}, object()
    company = SimpleNamespace(id=4, ticker="EXAMPLE", group_root_id=None)
    mocker.patch.object(routes, "_authorized_company", new_callable=AsyncMock, return_value=company)
    statement = SimpleNamespace(id=8)
    mocker.patch.object(routes, "get_statement", new_callable=AsyncMock, return_value=statement)
    assert await routes.get_company_financial_statement(4, "income", 2024, "quarterly", 2, user, db) is statement

    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=missing)
    with pytest.raises(HTTPException, match="missing"):
        await routes.get_company_financial_statement(4, "income", 2024, "annual", 0, user, db)

    importer = mocker.patch.object(routes, "import_statement", new_callable=AsyncMock, side_effect=ValueError("invalid period"))
    with pytest.raises(HTTPException) as error:
        await routes.import_company_financial_statement(object(), 4, "income", 2024, "quarterly", 2, True, user, db)
    assert error.value.status_code == 400
    assert importer.await_args.kwargs == {"refresh": True, "period_type": "quarterly", "period_number": 2}

    mocker.patch.object(routes, "import_statement", new_callable=AsyncMock, side_effect=YFinanceFetchError("provider offline"))
    with pytest.raises(HTTPException) as error:
        await routes.import_company_financial_statement(object(), 4, "cash_flow", 2024, "annual", 0, False, user, db)
    assert error.value.status_code == 502
