"""Deterministic balance-sheet calculations.

The values in this module are calculated only from imported BalanceSheet rows.
Thresholds are intentionally review triggers, not accounting conclusions.
"""

from .analysis_schema import (
    AnalysisMetric,
    AnalysisWarning,
    BalanceSheetAnalysisResponse,
    DataQualityIssue,
    SourceYear,
    TrendPoint,
)
from .balance_sheet_model import BalanceSheet

UNIT = "reported currency units"
THRESHOLDS: dict[str, float | int] = {
    "material_change_pct": 0.20,
    "large_movement_pct": 0.50,
    "consecutive_falling_cash_years": 2,
    "growth_outpaces_assets_pct": 0.20,
    "minimum_current_ratio": 1.0,
    "minimum_quick_ratio": 0.8,
    "maximum_debt_to_assets": 0.80,
    "maximum_net_debt_to_equity": 2.0,
    "minimum_cash_ratio": 0.10,
    "minimum_equity_ratio": 0.20,
    "maximum_long_term_debt_share": 0.75,
}

_TREND_FIELDS: dict[str, tuple[str, ...]] = {
    "total_assets": ("total_assets",),
    "total_liabilities": ("total_liabilities_net_minority_interest",),
    "stockholders_equity": ("stockholders_equity",),
    "cash_and_short_term_investments": ("cash_cash_equivalents_and_short_term_investments", "cash_and_cash_equivalents", "other_short_term_investments"),
    "current_assets": ("current_assets",),
    "current_liabilities": ("current_liabilities",),
    "total_debt": ("total_debt",),
    "net_debt": ("net_debt",),
    "receivables": ("receivables", "accounts_receivable", "other_receivables"),
    "inventory": ("inventory",),
}

_SOURCE_FIELDS = tuple(dict.fromkeys(field for fields in _TREND_FIELDS.values() for field in fields)) + (
    "long_term_debt",
    "net_ppe",
    "gross_ppe",
)


def _first_value(row: BalanceSheet, fields: tuple[str, ...]) -> tuple[float | None, list[str]]:
    for field in fields:
        value = getattr(row, field, None)
        if value is not None:
            return float(value), [field]
    return None, list(fields)


def _sum_values(row: BalanceSheet, fields: tuple[str, ...]) -> tuple[float | None, list[str]]:
    values = [(field, getattr(row, field, None)) for field in fields]
    present = [(field, float(value)) for field, value in values if value is not None]
    if not present:
        return None, list(fields)
    return sum(value for _, value in present), [field for field, _ in present]


def _cash(row: BalanceSheet) -> tuple[float | None, list[str]]:
    combined = getattr(row, "cash_cash_equivalents_and_short_term_investments", None)
    if combined is not None:
        return float(combined), ["cash_cash_equivalents_and_short_term_investments"]
    return _sum_values(row, ("cash_and_cash_equivalents", "other_short_term_investments"))


def _receivables(row: BalanceSheet) -> tuple[float | None, list[str]]:
    return _first_value(row, ("receivables", "accounts_receivable", "other_receivables"))


def _net_debt(row: BalanceSheet) -> tuple[float | None, list[str]]:
    reported = getattr(row, "net_debt", None)
    if reported is not None:
        return float(reported), ["net_debt"]
    debt = getattr(row, "total_debt", None)
    cash, cash_fields = _cash(row)
    if debt is not None and cash is not None:
        return float(debt) - cash, ["total_debt", *cash_fields]
    return None, ["net_debt", "total_debt", *cash_fields]


def _value(row: BalanceSheet, metric: str) -> tuple[float | None, list[str]]:
    if metric == "cash_and_short_term_investments":
        return _cash(row)
    if metric == "receivables":
        return _receivables(row)
    if metric == "net_debt":
        return _net_debt(row)
    return _first_value(row, _TREND_FIELDS[metric])


def _metric(value: float | None, source_fields: list[str], *, denominator: str | None = None, note: str | None = None, unit: str = UNIT) -> AnalysisMetric:
    return AnalysisMetric(
        value=value,
        status="available" if value is not None else "unavailable",
        unit=unit,
        denominator=denominator,
        source_fields=source_fields,
        note=note,
    )


def _ratio(
    numerator: float | None,
    denominator: float | None,
    numerator_fields: list[str],
    denominator_name: str,
    denominator_fields: list[str] | None = None,
) -> AnalysisMetric:
    source_fields = list(dict.fromkeys([*numerator_fields, *(denominator_fields or [])]))
    if numerator is None or denominator is None:
        return _metric(None, source_fields, denominator=denominator_name, note="Required source field is missing", unit="ratio")
    if denominator <= 0:
        return _metric(None, source_fields, denominator=denominator_name, note="Denominator must be positive", unit="ratio")
    return _metric(numerator / denominator, source_fields, denominator=denominator_name, unit="ratio")


def _pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / abs(previous) * 100


def _trend(rows: list[BalanceSheet], metric: str) -> list[TrendPoint]:
    points: list[TrendPoint] = []
    previous: float | None = None
    for row in rows:
        value, source_fields = _value(row, metric)
        points.append(
            TrendPoint(
                year=row.year,
                value=value,
                yoy_change_pct=_pct_change(value, previous),
                status="available" if value is not None else "unavailable",
                unit=UNIT,
                source_fields=source_fields,
            )
        )
        previous = value
    return points


def _series_value(series: dict[str, list[TrendPoint]], metric: str, year: int) -> float | None:
    point = next((item for item in series[metric] if item.year == year), None)
    return point.value if point else None


def _row_quality(row: BalanceSheet) -> list[DataQualityIssue]:
    missing = [field for field in ("total_assets", "total_liabilities_net_minority_interest", "stockholders_equity") if getattr(row, field, None) is None]
    issues: list[DataQualityIssue] = []
    if missing:
        issues.append(DataQualityIssue(code="missing_core_fields", severity="warning", year=row.year, fields=missing, message="Core balance-sheet fields are missing; related metrics may be unavailable."))
    negative = [
        field for field in ("total_assets", "total_liabilities_net_minority_interest")
        if (value := getattr(row, field, None)) is not None and value < 0
    ]
    if negative:
        issues.append(DataQualityIssue(code="negative_core_value", severity="warning", year=row.year, fields=negative, message="A core reported balance-sheet total is negative; percentage and ratio interpretations may be limited."))
    return issues


def _warnings(rows: list[BalanceSheet], trends: dict[str, list[TrendPoint]], metrics: dict[str, list[AnalysisMetric]], thresholds: dict[str, float | int]) -> list[AnalysisWarning]:
    warnings: list[AnalysisWarning] = []
    cash_points = trends["cash_and_short_term_investments"]
    falling_run_years: list[int] = []
    current_falling_run: list[int] = []
    for cash_previous, cash_current in zip(cash_points[:-1], cash_points[1:], strict=True):
        if cash_previous.value is not None and cash_current.value is not None and cash_current.value < cash_previous.value:
            current_falling_run.append(cash_current.year)
            if len(current_falling_run) >= thresholds["consecutive_falling_cash_years"]:
                falling_run_years = current_falling_run.copy()
        else:
            current_falling_run = []
    if falling_run_years:
        warnings.append(AnalysisWarning(type="falling_cash", severity="review", message="Cash and short-term investments fell across consecutive fiscal years; flag for review.", years=falling_run_years, evidence={"start_value": next((point.value for point in cash_points if point.year == falling_run_years[0] - 1), None), "end_value": next((point.value for point in cash_points if point.year == falling_run_years[-1]), None)}))

    debt_points = trends["total_debt"]
    asset_points = trends["total_assets"]
    for point in debt_points[1:]:
        if point.yoy_change_pct is not None and point.yoy_change_pct >= thresholds["material_change_pct"] * 100:
            warnings.append(AnalysisWarning(type="rising_debt", severity="review", message="Total debt increased materially year over year; flag for review.", years=[point.year], evidence={"yoy_change_pct": point.yoy_change_pct, "threshold_pct": thresholds["material_change_pct"] * 100}))
            break
    for debt_point, asset_point in zip(debt_points[1:], asset_points[1:], strict=True):
        if (
            debt_point.yoy_change_pct is not None
            and asset_point.yoy_change_pct is not None
            and debt_point.yoy_change_pct - asset_point.yoy_change_pct >= thresholds["growth_outpaces_assets_pct"] * 100
        ):
            warnings.append(AnalysisWarning(type="debt_growth_outpaced_assets", severity="review", message="Debt growth outpaced total-asset growth materially; flag for review.", years=[debt_point.year], evidence={"debt_yoy_change_pct": debt_point.yoy_change_pct, "assets_yoy_change_pct": asset_point.yoy_change_pct, "threshold_difference_pct": thresholds["growth_outpaces_assets_pct"] * 100}))
            break

    wc_points = metrics["working_capital"]
    years = [row.year for row in rows]
    for year, wc_point in zip(years, wc_points, strict=True):
        if wc_point.value is not None and wc_point.value < 0:
            warnings.append(AnalysisWarning(type="negative_working_capital", severity="review", message="Working capital is negative; flag for review.", years=[year], evidence={"working_capital": wc_point.value}))
            break

    covenant_rules = (
        ("minimum_current_ratio", "current_ratio", lambda value, limit: value < limit, "Current ratio is below the configured management threshold."),
        ("minimum_quick_ratio", "quick_ratio", lambda value, limit: value < limit, "Quick ratio is below the configured management threshold."),
        ("maximum_debt_to_assets", "debt_to_assets", lambda value, limit: value > limit, "Debt-to-assets is above the configured management threshold."),
        ("maximum_net_debt_to_equity", "net_debt_to_equity", lambda value, limit: value > limit, "Net debt-to-equity is above the configured management threshold."),
        ("minimum_cash_ratio", "cash_ratio", lambda value, limit: value < limit, "Cash ratio is below the configured management threshold."),
        ("minimum_equity_ratio", "equity_ratio", lambda value, limit: value < limit, "Equity ratio is below the configured management threshold."),
        ("maximum_long_term_debt_share", "long_term_debt_share", lambda value, limit: value > limit, "Long-term debt share is above the configured management threshold."),
    )
    for threshold_name, metric_name, triggered, message in covenant_rules:
        for year, metric in zip(years, metrics[metric_name], strict=True):
            limit = thresholds[threshold_name]
            if metric.value is not None and triggered(metric.value, limit):
                warnings.append(AnalysisWarning(type=f"covenant_{metric_name}", severity="review", message=message, years=[year], evidence={"metric": metric.value, "threshold": limit, "threshold_name": threshold_name}))
    for previous_year, current_year, wc_previous, wc_current in zip(
        years[:-1], years[1:], wc_points[:-1], wc_points[1:], strict=True
    ):
        if wc_previous.value is not None and wc_current.value is not None and wc_current.value < wc_previous.value:
            warnings.append(AnalysisWarning(type="deteriorating_working_capital", severity="review", message="Working capital declined year over year; flag for review.", years=[previous_year, current_year], evidence={"previous": wc_previous.value, "current": wc_current.value}))
            break

    equity_points = trends["stockholders_equity"]
    equity_decline = next((point for point in equity_points[1:] if point.yoy_change_pct is not None and point.yoy_change_pct <= -thresholds["material_change_pct"] * 100), None)
    if equity_decline:
        warnings.append(AnalysisWarning(type="falling_equity", severity="review", message="Stockholders' equity declined materially year over year; flag for review.", years=[equity_decline.year], evidence={"yoy_change_pct": equity_decline.yoy_change_pct, "threshold_pct": -thresholds["material_change_pct"] * 100}))

    for component in ("receivables", "inventory"):
        component_points = trends[component]
        asset_points = trends["total_assets"]
        for asset, item in zip(asset_points[1:], component_points[1:], strict=True):
            if item.yoy_change_pct is not None and asset.yoy_change_pct is not None and item.yoy_change_pct - asset.yoy_change_pct >= thresholds["material_change_pct"] * 100:
                warnings.append(AnalysisWarning(type=f"{component}_growth_outpaced_assets", severity="review", message=f"{component.replace('_', ' ').capitalize()} growth outpaced total assets materially; flag for review.", years=[item.year], evidence={"component_yoy_pct": item.yoy_change_pct, "assets_yoy_pct": asset.yoy_change_pct, "threshold_difference_pct": thresholds["material_change_pct"] * 100}))
                break

    for metric_name in ("total_assets", "total_liabilities", "stockholders_equity"):
        for point in trends[metric_name][1:]:
            if point.yoy_change_pct is not None and abs(point.yoy_change_pct) >= thresholds["large_movement_pct"] * 100:
                warnings.append(AnalysisWarning(type="large_reported_movement", severity="review", message=f"{metric_name.replace('_', ' ').capitalize()} moved by at least {thresholds['large_movement_pct'] * 100:.0f}% year over year; investigate the reported line items.", years=[point.year], evidence={"metric": metric_name, "yoy_change_pct": point.yoy_change_pct, "threshold_pct": thresholds["large_movement_pct"] * 100}))
    return warnings


def calculate_analysis(company_id: int, rows: list[BalanceSheet], requested_years: list[int] | None = None, threshold_overrides: dict[str, float] | None = None) -> BalanceSheetAnalysisResponse:
    thresholds = {**THRESHOLDS, **(threshold_overrides or {})}
    rows = sorted(rows, key=lambda row: row.year)
    years = [row.year for row in rows]
    trends = {name: _trend(rows, name) for name in _TREND_FIELDS}

    metric_names = ("current_ratio", "quick_ratio", "cash_ratio", "working_capital", "debt_to_equity", "debt_to_assets", "liabilities_to_assets", "equity_ratio", "net_debt_to_equity", "long_term_debt_share")
    metrics: dict[str, list[AnalysisMetric]] = {name: [] for name in metric_names}
    composition_names = ("cash_as_pct_assets", "receivables_as_pct_assets", "inventory_as_pct_assets", "fixed_assets_as_pct_assets", "current_assets_as_pct_assets", "current_liabilities_as_pct_liabilities", "current_liabilities_as_pct_assets", "equity_as_pct_assets", "debt_as_pct_assets")
    composition: dict[str, list[AnalysisMetric]] = {name: [] for name in composition_names}

    for row in rows:
        assets, assets_fields = _value(row, "total_assets")
        liabilities, liabilities_fields = _value(row, "total_liabilities")
        equity, equity_fields = _value(row, "stockholders_equity")
        current_assets, current_assets_fields = _value(row, "current_assets")
        current_liabilities, current_liabilities_fields = _value(row, "current_liabilities")
        debt, debt_fields = _value(row, "total_debt")
        net_debt, net_debt_fields = _value(row, "net_debt")
        cash, cash_fields = _value(row, "cash_and_short_term_investments")
        receivables, receivables_fields = _value(row, "receivables")
        inventory, inventory_fields = _value(row, "inventory")
        fixed_assets, fixed_assets_fields = _first_value(row, ("net_ppe", "gross_ppe"))
        working_capital = current_assets - current_liabilities if current_assets is not None and current_liabilities is not None else None
        metrics["current_ratio"].append(_ratio(current_assets, current_liabilities, current_assets_fields, "current liabilities", current_liabilities_fields))
        quick_numerator = cash + receivables if cash is not None and receivables is not None else None
        metrics["quick_ratio"].append(_ratio(quick_numerator, current_liabilities, [*cash_fields, *receivables_fields], "current liabilities; cash and receivables", current_liabilities_fields))
        metrics["cash_ratio"].append(_ratio(cash, current_liabilities, cash_fields, "current liabilities", current_liabilities_fields))
        metrics["working_capital"].append(_metric(working_capital, [*current_assets_fields, *current_liabilities_fields], note="Current assets less current liabilities"))
        metrics["debt_to_equity"].append(_ratio(debt, equity, debt_fields, "stockholders' equity", equity_fields))
        metrics["debt_to_assets"].append(_ratio(debt, assets, debt_fields, "total assets", assets_fields))
        metrics["liabilities_to_assets"].append(_ratio(liabilities, assets, liabilities_fields, "total assets", assets_fields))
        metrics["equity_ratio"].append(_ratio(equity, assets, equity_fields, "total assets", assets_fields))
        metrics["net_debt_to_equity"].append(_ratio(net_debt, equity, net_debt_fields, "stockholders' equity", equity_fields))
        metrics["long_term_debt_share"].append(_ratio(getattr(row, "long_term_debt", None), debt, ["long_term_debt"], "total debt", debt_fields))
        composition["cash_as_pct_assets"].append(_metric(cash / assets * 100 if cash is not None and assets is not None and assets > 0 else None, cash_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["receivables_as_pct_assets"].append(_metric(receivables / assets * 100 if receivables is not None and assets and assets > 0 else None, receivables_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["inventory_as_pct_assets"].append(_metric(inventory / assets * 100 if inventory is not None and assets and assets > 0 else None, inventory_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["fixed_assets_as_pct_assets"].append(_metric(fixed_assets / assets * 100 if fixed_assets is not None and assets and assets > 0 else None, fixed_assets_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["current_assets_as_pct_assets"].append(_metric(current_assets / assets * 100 if current_assets is not None and assets and assets > 0 else None, current_assets_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["current_liabilities_as_pct_liabilities"].append(_metric(current_liabilities / liabilities * 100 if current_liabilities is not None and liabilities and liabilities > 0 else None, current_liabilities_fields, denominator="total liabilities", note="Percentage of total liabilities", unit="percent"))
        composition["current_liabilities_as_pct_assets"].append(_metric(current_liabilities / assets * 100 if current_liabilities is not None and assets and assets > 0 else None, current_liabilities_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["equity_as_pct_assets"].append(_metric(equity / assets * 100 if equity is not None and assets and assets > 0 else None, equity_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))
        composition["debt_as_pct_assets"].append(_metric(debt / assets * 100 if debt is not None and assets and assets > 0 else None, debt_fields, denominator="total assets", note="Percentage of total assets", unit="percent"))

    data_quality = [_row_quality(row) for row in rows]
    quality = [issue for issues in data_quality for issue in issues]
    if requested_years:
        missing_years = sorted(set(requested_years) - set(years))
        if missing_years:
            quality.append(DataQualityIssue(code="requested_year_missing", severity="warning", fields=[], message=f"No imported balance-sheet row is available for fiscal year(s): {', '.join(map(str, missing_years))}."))
            missing_warning = AnalysisWarning(type="missing_filings", severity="review", message="One or more requested fiscal periods are missing; confirm whether filings are unavailable or import has not run.", years=missing_years, evidence={"missing_year_count": len(missing_years)})
        else:
            missing_warning = None
    else:
        missing_warning = None
    for metric_name, values in {**metrics, **composition}.items():
        if values and all(item.status == "unavailable" for item in values):
            quality.append(DataQualityIssue(code="metric_unavailable", severity="warning", fields=[], message=f"{metric_name.replace('_', ' ').capitalize()} cannot be calculated from the imported fields."))

    source_values = [SourceYear(year=row.year, values={field: getattr(row, field, None) for field in _SOURCE_FIELDS}) for row in rows]
    warnings = _warnings(rows, trends, metrics, thresholds)
    if missing_warning is not None:
        warnings.append(missing_warning)
    return BalanceSheetAnalysisResponse(company_id=company_id, requested_years=requested_years, fiscal_years=years, unit=UNIT, thresholds=thresholds, trends=trends, metrics=metrics, composition=composition, source_values=source_values, warnings=warnings, data_quality=quality)


def analysis_context(analysis: BalanceSheetAnalysisResponse, company_name: str, ticker: str) -> str:
    """Serialize deterministic source values, metrics, and warnings for chat."""
    lines = [f"Company: {company_name} ({ticker})", f"Fiscal years included: {', '.join(map(str, analysis.fiscal_years)) or 'none'}", f"Units: {analysis.unit}", "Source figures by fiscal year:"]
    for source in analysis.source_values:
        lines.append(f"  {source.year}: " + ", ".join(f"[source:balance_sheet:FY{source.year}:{key}] {key}={value:,.2f}" for key, value in source.values.items() if value is not None))
    lines.append("Deterministic calculated metrics:")
    for name, values in {**analysis.metrics, **analysis.composition}.items():
        rendered = ", ".join(f"{analysis.fiscal_years[index]}={item.value:.4f}" for index, item in enumerate(values) if item.value is not None)
        lines.append(f"  {name}: {rendered or 'unavailable'}")
    lines.append("Deterministic warnings:")
    if analysis.warnings:
        lines.extend(f"  - {warning.type}: {warning.message}; evidence={warning.evidence}" for warning in analysis.warnings)
    else:
        lines.append("  - none")
    if analysis.data_quality:
        lines.append("Data-quality limitations:")
        lines.extend(f"  - {issue.message}" for issue in analysis.data_quality)
    return "\n".join(lines)
