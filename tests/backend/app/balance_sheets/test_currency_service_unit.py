from datetime import date

from backend.app.balance_sheets.balance_sheet_model import BalanceSheet
from backend.app.balance_sheets.currency_model import CurrencyRate
from backend.app.balance_sheets.currency_service import normalize_rows


def test_normalize_rows_applies_explicit_rate_and_records_source():
    row = BalanceSheet(company_id=1, year=2024, currency_code="USD", period_end_date=date(2024, 12, 31), total_assets=100, unit_scale=1)
    rate = CurrencyRate(company_id=1, source_currency="USD", target_currency="EUR", effective_date=date(2024, 12, 1), rate=0.9, source="ECB", source_url="https://example.test/rates")
    rows, metadata = normalize_rows([row], "EUR", [rate])
    assert rows[0].total_assets == 90
    assert metadata["target_currency"] == "EUR"
    assert metadata["used_rates"][0]["source"] == "ECB"


def test_normalize_rows_reports_unknown_currency_or_rate():
    row = BalanceSheet(company_id=1, year=2024, currency_code=None, total_assets=100)
    rows, metadata = normalize_rows([row], "EUR", [])
    assert rows[0].total_assets == 100
    assert metadata["unavailable_years"] == [2024]
