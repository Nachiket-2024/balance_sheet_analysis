from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from backend.app.api.balance_sheet_routes import balance_sheet_routes as routes
from backend.app.balance_sheets.balance_sheet_crud import YFinanceFetchError


async def passthrough(value, *_args, **_kwargs):
    return await value if hasattr(value, "__await__") else value


@pytest.mark.asyncio
async def test_list_get_and_export_company_periods(mocker):
    user, db = {"email": "analyst@example.com"}, object()
    company = SimpleNamespace(id=6, ticker="EXAMPLE", group_root_id=None)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=passthrough)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    row_fields = {field: None for field in [
            "id", "company_id", "year", "period_end_date", "period_type", "source_provider", "source_url",
            "currency_code", "unit_scale", "data_quality_status", "imported_at", "version", "total_assets",
            "total_liabilities_net_minority_interest", "stockholders_equity", "total_debt", "net_debt", "current_assets",
            "current_liabilities", "working_capital", "cash_and_cash_equivalents",
        ]}
    row_fields.update(id=1, company_id=6, year=2024, period_end_date=date(2024, 12, 31), imported_at=datetime(2025, 1, 2), period_type="annual", total_assets=100)
    rows = [SimpleNamespace(**row_fields)]
    listed = mocker.patch.object(routes, "list_balance_sheets_for_company", new_callable=AsyncMock, return_value=rows)
    assert await routes.list_company_balance_sheets(6, user, db) == rows

    mocker.patch.object(routes, "get_balance_sheet", new_callable=AsyncMock, return_value=rows[0])
    assert await routes.get_company_balance_sheet(6, 2024, user, db) is rows[0]

    response = await routes.export_company_balance_sheets(6, user, db)
    csv_text = response.body.decode()
    assert response.media_type.startswith("text/csv")
    assert "company-6-balance-sheets.csv" in response.headers["Content-Disposition"]
    assert "2024-12-31" in csv_text
    assert "100" in csv_text
    assert listed.await_count == 2


@pytest.mark.asyncio
async def test_import_and_delete_map_errors_and_persist_removal(mocker):
    user, db = {"email": "analyst@example.com"}, object()
    company = SimpleNamespace(id=6, ticker="EXAMPLE", group_root_id=None)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=passthrough)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)

    mocker.patch.object(routes, "import_balance_sheet", new_callable=AsyncMock, side_effect=ValueError("already exists"))
    with pytest.raises(HTTPException) as error:
        await routes.create_company_balance_sheet(object(), 6, 2024, True, user, db)
    assert error.value.status_code == 400

    mocker.patch.object(routes, "import_balance_sheet", new_callable=AsyncMock, side_effect=YFinanceFetchError("offline"))
    with pytest.raises(HTTPException) as error:
        await routes.create_company_balance_sheet(object(), 6, 2024, False, user, db)
    assert error.value.status_code == 502

    row = SimpleNamespace(id=2)
    mocker.patch.object(routes, "get_balance_sheet", new_callable=AsyncMock, return_value=row)
    delete = mocker.patch.object(routes, "delete_balance_sheet_row", new_callable=AsyncMock)
    await routes.delete_company_balance_sheet(6, 2024, user, db)
    delete.assert_awaited_once_with(row, db)
