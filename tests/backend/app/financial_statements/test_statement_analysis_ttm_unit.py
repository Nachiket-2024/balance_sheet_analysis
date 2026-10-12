from types import SimpleNamespace

from backend.app.financial_statements.statement_analysis import (
    calculate_statement_analysis,
)


def test_statement_analysis_builds_ttm_from_four_quarters():
    rows = []
    for quarter in range(1, 5):
        rows.extend([
            SimpleNamespace(year=2024, period_type="quarterly", period_number=quarter, statement_type="income", total_revenue=100, operating_income=20, net_income=10),
            SimpleNamespace(year=2024, period_type="quarterly", period_number=quarter, statement_type="cash_flow", operating_cash_flow=15, capital_expenditure=-5, free_cash_flow=10),
        ])
    result = calculate_statement_analysis(rows)
    assert result["ttm"] == [{
        "as_of": "Q4 FY2024", "revenue": 400, "operating_margin": 0.2,
        "cash_conversion": 1.5, "free_cash_flow": 40,
        "free_cash_flow_reconciliation": 0,
    }]
