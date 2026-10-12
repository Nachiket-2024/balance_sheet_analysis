import inspect
from datetime import UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from backend.app.api.analysis_routes import analysis_routes as routes
from backend.app.balance_sheets.analysis_schema import BalanceSheetAnalysisResponse


def company(company_id=1):
    return SimpleNamespace(id=company_id, name=f"Company {company_id}", ticker=f"C{company_id}", group_root_id=None)


async def resolve(value, *_args, **_kwargs):
    return await value if inspect.isawaitable(value) else value


@pytest.mark.asyncio
async def test_benchmark_rejects_invalid_metric_and_duplicate_companies(mocker):
    user, db = {"email": "user@example.com"}, object()
    with pytest.raises(HTTPException, match="Unsupported benchmark metric"):
        await routes.benchmark_company_balance_sheet_analysis([1, 2], "not_a_metric", None, None, user, db)
    with pytest.raises(HTTPException, match="must not contain duplicates"):
        await routes.benchmark_company_balance_sheet_analysis([1, 1], "total_assets", None, None, user, db)


@pytest.mark.asyncio
async def test_benchmark_builds_percentiles_for_missing_and_present_values(mocker):
    user, db = {"email": "user@example.com"}, object()
    mocker.patch.object(routes, "get_company_by_id", side_effect=[company(1), company(2), company(3)])
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    auth = mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    mocker.patch.object(routes, "list_balance_sheets_for_company_years", new_callable=AsyncMock, return_value=[])
    mocker.patch.object(routes, "get_or_create_settings", new_callable=AsyncMock, return_value=SimpleNamespace(target_currency=None, thresholds={}, display_scale=1))
    mocker.patch.object(routes, "calculate_analysis", side_effect=[
        SimpleNamespace(fiscal_years=[2024], trends={"total_assets": [SimpleNamespace(year=2024, value=10)]}),
        SimpleNamespace(fiscal_years=[2024], trends={"total_assets": [SimpleNamespace(year=2024, value=20)]}),
        SimpleNamespace(fiscal_years=[], trends={"total_assets": []}),
    ])

    result = await routes.benchmark_company_balance_sheet_analysis([1, 2, 3], "total_assets", None, None, user, db)

    assert [point.percentile for point in result.points] == [0.0, 50.0, None]
    assert auth.await_count == 3


@pytest.mark.asyncio
async def test_benchmark_uses_target_currency_and_display_scale(mocker):
    user, db = {"email": "reader@example.com"}, object()
    mocker.patch.object(routes, "get_company_by_id", side_effect=[company(1), company(2)])
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    rows = [object()]
    mocker.patch.object(routes, "list_balance_sheets_for_company_years", new_callable=AsyncMock, return_value=rows)
    mocker.patch.object(routes, "get_or_create_settings", new_callable=AsyncMock, return_value=SimpleNamespace(target_currency="USD", thresholds={}, display_scale=1000))
    mocker.patch.object(routes, "list_currency_rates", new_callable=AsyncMock, return_value=[])
    normalize = mocker.patch.object(routes, "normalize_rows", return_value=(rows, {}))
    mocker.patch.object(routes, "calculate_analysis", side_effect=[
        SimpleNamespace(fiscal_years=[2024], trends={"total_assets": [SimpleNamespace(year=2024, value=10)]}),
        SimpleNamespace(fiscal_years=[2024], trends={"total_assets": [SimpleNamespace(year=2024, value=20)]}),
    ])

    result = await routes.benchmark_company_balance_sheet_analysis([1, 2], "total_assets", 2024, None, user, db)

    assert result.unit == "USD units / 1000"
    assert normalize.call_count == 2


@pytest.mark.asyncio
async def test_compare_and_company_analysis_validate_access_and_normalize_currency(mocker):
    user, db = {"email": "user@example.com"}, object()
    with pytest.raises(HTTPException, match="must not contain duplicates"):
        await routes.compare_company_balance_sheet_analysis([1, 1], None, user, db)

    item = company(2)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=item)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    rows = [object()]
    mocker.patch.object(routes, "list_balance_sheets_for_company_years", new_callable=AsyncMock, return_value=rows)
    settings = SimpleNamespace(target_currency="USD", thresholds={"debt_ratio": 0.7}, display_scale=1000)
    mocker.patch.object(routes, "get_or_create_settings", new_callable=AsyncMock, return_value=settings)
    analysis = BalanceSheetAnalysisResponse(
        company_id=2,
        fiscal_years=[2024],
        unit="reported currency units",
        thresholds={"debt_ratio": 0.7},
        trends={},
        metrics={},
        composition={},
        source_values=[],
        warnings=[],
        data_quality=[],
    )
    calculate = mocker.patch.object(routes, "calculate_analysis", return_value=analysis)
    normalize = mocker.patch.object(routes, "normalize_rows", return_value=(["normalized"], {"target_currency": "USD", "display_scale": 1000}))
    mocker.patch.object(routes, "list_currency_rates", new_callable=AsyncMock, return_value=[])
    sync = mocker.patch.object(routes, "sync_analysis_alerts", new_callable=AsyncMock)

    detail = await routes.get_company_balance_sheet_analysis(2, [2024], None, user, db)
    assert detail.normalization["target_currency"] == "USD"
    assert detail.unit == "USD units / 1000"
    normalize.assert_called_once_with(rows, "USD", [], 1000)
    sync.assert_awaited_once_with(2, [], db)

    calculate.return_value = detail
    compared = await routes.compare_company_balance_sheet_analysis([2], [2024], user, db)
    assert compared.companies[0].company_id == 2
    calculate.assert_called()


@pytest.mark.asyncio
async def test_analysis_settings_update_records_history_and_maps_validation_error(mocker):
    user, db = {"email": "user@example.com"}, SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    item = company(7)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=item)
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    settings = SimpleNamespace(thresholds={}, target_currency=None, display_scale=1)
    mocker.patch.object(routes, "get_or_create_settings", new_callable=AsyncMock, return_value=settings)
    mocker.patch.object(routes, "effective_thresholds", return_value={"debt_ratio": 0.5})
    mocker.patch.object(routes, "validate_thresholds", return_value={"debt_ratio": 0.5})

    result = await routes.update_company_analysis_settings(7, SimpleNamespace(thresholds={"debt_ratio": 0.5}, target_currency="usd", display_scale=1000), user, db)
    assert result.target_currency == "USD"
    assert result.display_scale == 1000
    assert db.add.call_args.args[0].changed_by == user["email"]
    db.commit.assert_awaited_once()

    mocker.patch.object(routes, "validate_thresholds", side_effect=ValueError("invalid threshold"))
    with pytest.raises(HTTPException, match="invalid threshold"):
        await routes.update_company_analysis_settings(7, SimpleNamespace(thresholds={"bad": 1}, target_currency=None, display_scale=None), user, db)


@pytest.mark.asyncio
async def test_policy_update_normalizes_values_and_rejects_invalid_policy(mocker):
    user, db = {"email": "owner@example.com"}, SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company(5))
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    policy = SimpleNamespace(enabled=False, recipients=[], minimum_severity="review", escalation_after_hours=0, escalation_recipients=[])
    mocker.patch.object(routes, "get_or_create_policy", new_callable=AsyncMock, return_value=policy)

    result = await routes.update_company_analysis_notification_policy(5, SimpleNamespace(enabled=True, recipients=[" Owner@Example.com "], minimum_severity="info", escalation_after_hours=2, escalation_recipients=[]), user, db)
    assert result.enabled is True
    assert result.recipients == ["owner@example.com"]
    assert result.minimum_severity == "info"
    db.commit.assert_awaited_once()

    mocker.patch.object(routes, "validate_policy", side_effect=ValueError("bad recipient"))
    with pytest.raises(HTTPException, match="bad recipient"):
        await routes.update_company_analysis_notification_policy(5, SimpleNamespace(enabled=None, recipients=None, minimum_severity=None, escalation_after_hours=None, escalation_recipients=None), user, db)


@pytest.mark.asyncio
async def test_preference_update_and_alert_acknowledgement(mocker):
    user = {"email": "person@example.com"}
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock(), get=AsyncMock())
    preference = SimpleNamespace(email_enabled=True)
    mocker.patch.object(routes, "get_or_create_preference", new_callable=AsyncMock, return_value=preference)
    changed = await routes.update_analysis_notification_preferences(SimpleNamespace(email_enabled=False), user, db)
    assert changed.email_enabled is False

    alert = SimpleNamespace(id=3, company_id=4, status="open", acknowledged_at=None, acknowledged_by=None)
    db.get.return_value = alert
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company(4))
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    updated = await routes.update_analysis_alert(3, SimpleNamespace(status="acknowledged"), user, db)
    assert updated.status == "acknowledged"
    assert updated.acknowledged_by == user["email"]
    assert updated.acknowledged_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_settings_currency_rates_and_policy_read_endpoints(mocker):
    user = {"email": "owner@example.com"}
    db = SimpleNamespace(add=Mock(), execute=AsyncMock(), commit=AsyncMock(), refresh=AsyncMock())
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company(5))
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)
    mocker.patch.object(routes, "get_or_create_settings", new_callable=AsyncMock, return_value=SimpleNamespace(thresholds={"debt_ratio": 0.5}, target_currency="USD", display_scale=1000))
    mocker.patch.object(routes, "effective_thresholds", return_value={"debt_ratio": 0.5})

    settings = await routes.get_company_analysis_settings(5, user, db)
    assert settings.target_currency == "USD"
    assert settings.thresholds == {"debt_ratio": 0.5}

    rates = [SimpleNamespace(id=1)]
    mocker.patch.object(routes, "list_currency_rates", new_callable=AsyncMock, return_value=rates)
    assert await routes.get_company_currency_rates(5, user, db) == rates
    with pytest.raises(HTTPException, match="must differ"):
        await routes.add_company_currency_rate(5, SimpleNamespace(source_currency="usd", target_currency="USD"), user, db)

    policy = SimpleNamespace(company_id=5)
    mocker.patch.object(routes, "get_or_create_policy", new_callable=AsyncMock, return_value=policy)
    assert await routes.get_company_analysis_notification_policy(5, user, db) is policy

    preference = SimpleNamespace(user_email=user["email"])
    mocker.patch.object(routes, "get_or_create_preference", new_callable=AsyncMock, return_value=preference)
    assert await routes.get_analysis_notification_preferences(user, db) is preference


@pytest.mark.asyncio
async def test_analysis_alert_and_delivery_lists_include_query_results(mocker):
    user = {"email": "reader@example.com"}

    class Result:
        def scalars(self):
            return self

        def all(self):
            return ["alert", "delivery"]

    db = SimpleNamespace(execute=AsyncMock(return_value=Result()))
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company(8))
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)

    assert await routes.list_company_analysis_alerts(8, False, user, db) == ["alert", "delivery"]
    assert await routes.list_company_analysis_alerts(8, True, user, db) == ["alert", "delivery"]
    assert await routes.list_company_analysis_notification_deliveries(8, user, db) == ["alert", "delivery"]


@pytest.mark.asyncio
async def test_settings_history_and_currency_rate_creation(mocker):
    user = {"email": "owner@example.com"}

    class Result:
        def scalars(self):
            return self

        def all(self):
            return ["history"]

    db = SimpleNamespace(execute=AsyncMock(return_value=Result()), add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    mocker.patch.object(routes, "get_company_by_id", new_callable=AsyncMock, return_value=company(5))
    mocker.patch.object(routes, "get_or_404", new_callable=AsyncMock, side_effect=resolve)
    mocker.patch.object(routes.authorization_service, "require", new_callable=AsyncMock)

    assert await routes.get_company_analysis_settings_history(5, user, db) == ["history"]
    rate = await routes.add_company_currency_rate(5, SimpleNamespace(source_currency="aud", target_currency="usd", effective_date="2024-01-01", rate=0.65, source="manual", source_url=None), user, db)
    assert rate.source_currency == "AUD"
    assert rate.target_currency == "USD"
    db.commit.assert_awaited_once()
