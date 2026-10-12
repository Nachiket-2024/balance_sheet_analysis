from typing import Any

from .financial_statement_model import FinancialStatement


def calculate_statement_analysis(statements: list[FinancialStatement]) -> dict[str, Any]:
    income = {item.year: item for item in statements if item.period_type == "annual" and item.statement_type == "income"}
    cash_flow = {item.year: item for item in statements if item.period_type == "annual" and item.statement_type == "cash_flow"}
    years = sorted(set(income) | set(cash_flow))
    trends: list[dict[str, Any]] = []
    warnings: list[str] = []
    for year in years:
        income_row = income.get(year)
        previous_income_row = income.get(year - 1)
        cash_flow_row = cash_flow.get(year)
        revenue = income_row.total_revenue if income_row else None
        previous = previous_income_row.total_revenue if previous_income_row else None
        operating_income = income_row.operating_income if income_row else None
        net_income = income_row.net_income if income_row else None
        operating_cash_flow = cash_flow_row.operating_cash_flow if cash_flow_row else None
        free_cash_flow = cash_flow_row.free_cash_flow if cash_flow_row else None
        capex = cash_flow_row.capital_expenditure if cash_flow_row else None
        reconciliation = (
            operating_cash_flow + capex - free_cash_flow
            if operating_cash_flow is not None and capex is not None and free_cash_flow is not None
            else None
        )
        trends.append({
            "year": year,
            "revenue_growth": (revenue - previous) / abs(previous) if revenue is not None and previous not in (None, 0) else None,
            "operating_margin": operating_income / revenue if operating_income is not None and revenue not in (None, 0) else None,
            "cash_conversion": operating_cash_flow / net_income if operating_cash_flow is not None and net_income not in (None, 0) else None,
            "free_cash_flow_margin": free_cash_flow / revenue if free_cash_flow is not None and revenue not in (None, 0) else None,
            "free_cash_flow_reconciliation": reconciliation,
        })
        if revenue is not None and operating_income is not None and revenue != 0 and operating_income / revenue < 0:
            warnings.append(f"{year}: operating margin is negative")
        if operating_cash_flow is not None and net_income is not None and net_income > 0 and operating_cash_flow < 0:
            warnings.append(f"{year}: operating cash flow is negative while net income is positive")
        reconciliation = trends[-1]["free_cash_flow_reconciliation"]
        if reconciliation is not None and abs(reconciliation) > max(abs(free_cash_flow or 0) * 0.02, 1.0):
            warnings.append(f"{year}: free cash flow does not reconcile to operating cash flow and capital expenditure")
    quarter_groups: dict[tuple[int, int], dict[str, FinancialStatement]] = {}
    for item in statements:
        if item.period_type == "quarterly":
            quarter_groups.setdefault((item.year, item.period_number), {})[item.statement_type] = item
    quarterly = sorted(quarter_groups.items())
    ttm: list[dict[str, Any]] = []
    for index in range(3, len(quarterly)):
        window = quarterly[index - 3:index + 1]
        if any(set(period) != {"income", "cash_flow"} for _, period in window):
            continue
        by_type = {kind: [period[kind] for _, period in window] for kind in ("income", "cash_flow")}
        income_totals = {field: sum((getattr(item, field) or 0) for item in by_type["income"]) for field in ("total_revenue", "operating_income", "net_income")}
        cash_totals = {field: sum((getattr(item, field) or 0) for item in by_type["cash_flow"]) for field in ("operating_cash_flow", "capital_expenditure", "free_cash_flow")}
        revenue = income_totals["total_revenue"]
        ttm.append({
            "as_of": f"Q{window[-1][0][1]} FY{window[-1][0][0]}",
            "revenue": revenue,
            "operating_margin": income_totals["operating_income"] / revenue if revenue else None,
            "cash_conversion": cash_totals["operating_cash_flow"] / income_totals["net_income"] if income_totals["net_income"] else None,
            "free_cash_flow": cash_totals["free_cash_flow"],
            "free_cash_flow_reconciliation": cash_totals["operating_cash_flow"] + cash_totals["capital_expenditure"] - cash_totals["free_cash_flow"],
        })
    return {"years": years, "trends": trends, "ttm": ttm, "warnings": warnings}
