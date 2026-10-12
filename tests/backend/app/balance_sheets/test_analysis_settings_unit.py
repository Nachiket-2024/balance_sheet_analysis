from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.balance_sheets.analysis_models import (
    AnalysisAlert,
    CompanyAnalysisSettings,
)
from backend.app.balance_sheets.analysis_schema import AnalysisWarning
from backend.app.balance_sheets.analysis_service import THRESHOLDS
from backend.app.balance_sheets.analysis_settings import (
    effective_thresholds,
    get_or_create_settings,
    sync_analysis_alerts,
    validate_thresholds,
)


def test_validate_thresholds_accepts_known_values_and_rejects_unknown_keys():
    assert validate_thresholds({"material_change_pct": 0.1}) == {"material_change_pct": 0.1}
    with pytest.raises(ValueError, match="Unknown threshold"):
        validate_thresholds({"not_a_real_threshold": 0.2})
    with pytest.raises(ValueError, match="non-negative"):
        validate_thresholds({next(iter(THRESHOLDS)): -0.1})


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self.value or [])


@pytest.mark.asyncio
async def test_get_or_create_settings_and_effective_defaults():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result(None), Result(None)])
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    created = await get_or_create_settings(7, db)
    assert created.company_id == 7
    assert created.thresholds == {}
    assert effective_thresholds(created) == THRESHOLDS
    assert effective_thresholds(None) == THRESHOLDS
    assert db.add.call_count == 1
    db.commit.assert_awaited_once()

    existing = CompanyAnalysisSettings(company_id=7, thresholds={"material_change_pct": 0.05})
    db.execute.side_effect = [Result(existing)]
    assert await get_or_create_settings(7, db) is existing
    assert effective_thresholds(existing)["material_change_pct"] == 0.05
    assert db.add.call_count == 1


@pytest.mark.asyncio
async def test_sync_analysis_alerts_creates_and_reopens_matching_warning():
    warning = AnalysisWarning(
        type="falling_cash",
        severity="review",
        message="Cash decreased",
        years=[2024],
        evidence={"change_pct": -20},
    )
    existing = AnalysisAlert(
        company_id=7,
        alert_key="rising_debt:2023",
        alert_type="rising_debt",
        severity="review",
        message="Old",
        status="resolved",
        years=[2023],
        evidence={},
    )
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[Result(None), Result([existing])])
    db.add = MagicMock()
    db.commit = AsyncMock()

    await sync_analysis_alerts(7, [warning], db)

    created = db.add.call_args.args[0]
    assert created.alert_key == "falling_cash:2024"
    assert created.message == "Cash decreased"
    assert existing.status == "resolved"
    db.commit.assert_awaited_once()

    existing.alert_key = "falling_cash:2024"
    existing.status = "resolved"
    db.execute.side_effect = [Result(existing), Result([existing])]
    db.add.reset_mock()
    await sync_analysis_alerts(7, [warning], db)
    assert existing.status == "open"
    assert existing.message == "Cash decreased"
    assert existing.evidence == {"change_pct": -20}
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_sync_analysis_alerts_resolves_open_warnings_that_disappear():
    stale = AnalysisAlert(
        company_id=7,
        alert_key="falling_cash:2023",
        alert_type="falling_cash",
        severity="review",
        message="Stale",
        status="open",
    )
    db = MagicMock()
    db.execute = AsyncMock(return_value=Result([stale]))
    db.commit = AsyncMock()

    await sync_analysis_alerts(7, [], db)

    assert stale.status == "resolved"
    db.commit.assert_awaited_once()
