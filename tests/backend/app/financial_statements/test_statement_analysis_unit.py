from types import SimpleNamespace

from backend.app.financial_statements.statement_analysis import (
    calculate_statement_analysis,
)


def test_statement_analysis_calculates_margins_conversion_and_reconciliation():
    rows = [
        SimpleNamespace(year=2023, period_type="annual", statement_type="income", total_revenue=1000, operating_income=100, net_income=80),
        SimpleNamespace(year=2023, period_type="annual", statement_type="cash_flow", operating_cash_flow=120, capital_expenditure=-40, free_cash_flow=80),
    ]
    result = calculate_statement_analysis(rows)
    trend = result["trends"][0]
    assert trend["operating_margin"] == 0.1
    assert trend["cash_conversion"] == 1.5
    assert trend["free_cash_flow_reconciliation"] == 0
    assert result["warnings"] == []
