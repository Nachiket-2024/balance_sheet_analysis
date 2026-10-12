import pytest

from backend.app.balance_sheets.analysis_service import (
    analysis_context,
    calculate_analysis,
)
from backend.app.balance_sheets.balance_sheet_model import BalanceSheet


def row(year: int, **values) -> BalanceSheet:
    return BalanceSheet(company_id=7, year=year, **values)


def test_calculates_liquidity_leverage_composition_and_yoy_change():
    analysis = calculate_analysis(
        7,
        [
            row(2022, total_assets=100, total_liabilities_net_minority_interest=60, stockholders_equity=40, current_assets=50, current_liabilities=25, total_debt=20, net_debt=10, cash_cash_equivalents_and_short_term_investments=10, receivables=15, inventory=20, long_term_debt=15, net_ppe=30),
            row(2023, total_assets=120, total_liabilities_net_minority_interest=72, stockholders_equity=48, current_assets=60, current_liabilities=30, total_debt=30, net_debt=20, cash_cash_equivalents_and_short_term_investments=8, receivables=18, inventory=22, long_term_debt=20, net_ppe=35),
        ],
    )

    assert analysis.metrics["current_ratio"][1].value == pytest.approx(2)
    assert analysis.metrics["quick_ratio"][1].value == pytest.approx(26 / 30)
    assert analysis.metrics["working_capital"][1].value == pytest.approx(30)
    assert analysis.metrics["debt_to_equity"][1].value == pytest.approx(30 / 48)
    assert analysis.composition["cash_as_pct_assets"][1].value == pytest.approx(8 / 120 * 100)
    assert analysis.trends["total_assets"][1].yoy_change_pct == pytest.approx(20)
    assert analysis.source_values[1].values["total_assets"] == 120


def test_zero_denominator_and_missing_source_are_unavailable():
    analysis = calculate_analysis(
        7,
        [row(2024, total_assets=0, current_assets=20, current_liabilities=0, total_debt=5, stockholders_equity=0)],
    )

    assert analysis.metrics["current_ratio"][0].status == "unavailable"
    assert analysis.metrics["current_ratio"][0].note == "Denominator must be positive"
    assert analysis.metrics["debt_to_equity"][0].status == "unavailable"
    assert analysis.composition["cash_as_pct_assets"][0].status == "unavailable"
    assert any(issue.code == "missing_core_fields" for issue in analysis.data_quality)


def test_negative_denominators_are_not_presented_as_ratios():
    analysis = calculate_analysis(
        7,
        [row(2024, total_assets=100, total_liabilities_net_minority_interest=130, stockholders_equity=-30, current_assets=20, current_liabilities=30, total_debt=20)],
    )
    assert analysis.metrics["debt_to_equity"][0].status == "unavailable"
    assert analysis.metrics["debt_to_assets"][0].value == pytest.approx(0.2)
    assert any(warning.type == "negative_working_capital" for warning in analysis.warnings)


def test_warning_thresholds_and_requested_missing_year_are_explicit():
    analysis = calculate_analysis(
        7,
        [
            row(2022, total_assets=100, current_assets=40, current_liabilities=50, total_debt=10, cash_cash_equivalents_and_short_term_investments=30),
            row(2023, total_assets=100, current_assets=40, current_liabilities=50, total_debt=13, cash_cash_equivalents_and_short_term_investments=20),
            row(2024, total_assets=100, current_assets=40, current_liabilities=50, total_debt=16, cash_cash_equivalents_and_short_term_investments=10),
        ],
        requested_years=[2022, 2023, 2024, 2025],
    )
    warning_types = {warning.type for warning in analysis.warnings}
    assert "falling_cash" in warning_types
    assert "rising_debt" in warning_types
    assert any(issue.code == "requested_year_missing" for issue in analysis.data_quality)
    assert analysis.thresholds["material_change_pct"] == 0.20


def test_company_threshold_override_changes_warning_boundary():
    analysis = calculate_analysis(
        7,
        [
            row(2022, total_assets=100, total_debt=10),
            row(2023, total_assets=100, total_debt=11),
        ],
        threshold_overrides={"material_change_pct": 0.05},
    )
    assert analysis.thresholds["material_change_pct"] == 0.05
    assert any(warning.type == "rising_debt" for warning in analysis.warnings)


def test_management_covenant_thresholds_create_explicit_alertable_warnings():
    analysis = calculate_analysis(
        7,
        [row(2024, current_assets=40, current_liabilities=50, total_assets=100, total_debt=90, cash_cash_equivalents_and_short_term_investments=2)],
        threshold_overrides={"minimum_current_ratio": 1.0, "maximum_debt_to_assets": 0.8, "minimum_cash_ratio": 0.1},
    )
    warning_types = {warning.type for warning in analysis.warnings}
    assert {"covenant_current_ratio", "covenant_debt_to_assets", "covenant_cash_ratio"} <= warning_types


def test_extended_covenants_cover_quick_ratio_leverage_equity_and_debt_maturity():
    analysis = calculate_analysis(
        7,
        [
            row(
                2024,
                current_assets=40,
                current_liabilities=50,
                total_assets=100,
                total_debt=90,
                net_debt=80,
                stockholders_equity=10,
                cash_cash_equivalents_and_short_term_investments=2,
                receivables=3,
                long_term_debt=80,
            )
        ],
        threshold_overrides={
            "minimum_quick_ratio": 0.8,
            "maximum_net_debt_to_equity": 2.0,
            "minimum_equity_ratio": 0.2,
            "maximum_long_term_debt_share": 0.75,
        },
    )
    warning_types = {warning.type for warning in analysis.warnings}
    assert {
        "covenant_quick_ratio",
        "covenant_net_debt_to_equity",
        "covenant_equity_ratio",
        "covenant_long_term_debt_share",
    } <= warning_types


def test_cash_warning_requires_a_consecutive_run_and_debt_can_outpace_assets():
    analysis = calculate_analysis(
        7,
        [
            row(2021, total_assets=100, total_debt=10, cash_cash_equivalents_and_short_term_investments=30),
            row(2022, total_assets=110, total_debt=20, cash_cash_equivalents_and_short_term_investments=20),
            row(2023, total_assets=120, total_debt=22, cash_cash_equivalents_and_short_term_investments=25),
            row(2024, total_assets=130, total_debt=40, cash_cash_equivalents_and_short_term_investments=15),
        ],
    )

    warning_types = {warning.type for warning in analysis.warnings}
    assert "falling_cash" not in warning_types
    assert "debt_growth_outpaced_assets" in warning_types


def test_falling_equity_warning_identifies_the_fiscal_year_and_evidence():
    analysis = calculate_analysis(
        7,
        [
            row(2022, total_assets=100, stockholders_equity=50),
            row(2023, total_assets=100, stockholders_equity=35),
        ],
    )

    warning = next(item for item in analysis.warnings if item.type == "falling_equity")
    assert warning.years == [2023]
    assert warning.evidence["yoy_change_pct"] == pytest.approx(-30)


def test_one_year_has_no_yoy_change_and_unavailable_metrics_are_honest():
    analysis = calculate_analysis(7, [row(2024, total_assets=100)])
    assert analysis.trends["total_assets"][0].yoy_change_pct is None
    assert analysis.metrics["quick_ratio"][0].status == "unavailable"
    assert analysis.fiscal_years == [2024]


def test_uses_fallback_fields_and_derives_net_debt_when_reported_values_are_absent():
    analysis = calculate_analysis(
        7,
        [
            row(
                2024,
                total_assets=100,
                total_liabilities_net_minority_interest=40,
                stockholders_equity=60,
                total_debt=30,
                cash_and_cash_equivalents=8,
                other_short_term_investments=2,
                accounts_receivable=15,
                gross_ppe=25,
                current_assets=50,
                current_liabilities=20,
            )
        ],
    )

    assert analysis.trends["cash_and_short_term_investments"][0].value == 10
    assert analysis.trends["net_debt"][0].value == 20
    assert analysis.trends["receivables"][0].value == 15
    assert analysis.composition["fixed_assets_as_pct_assets"][0].value == 25
    assert analysis.metrics["net_debt_to_equity"][0].source_fields == [
        "total_debt",
        "cash_and_cash_equivalents",
        "other_short_term_investments",
        "stockholders_equity",
    ]


def test_emits_deterioration_component_growth_and_large_movement_warnings():
    analysis = calculate_analysis(
        7,
        [
            row(2022, total_assets=100, total_liabilities_net_minority_interest=40, stockholders_equity=60, current_assets=60, current_liabilities=20, receivables=10, inventory=10),
            row(2023, total_assets=160, total_liabilities_net_minority_interest=40, stockholders_equity=60, current_assets=50, current_liabilities=30, receivables=30, inventory=30),
        ],
    )

    warning_types = [warning.type for warning in analysis.warnings]
    assert "deteriorating_working_capital" in warning_types
    assert "receivables_growth_outpaced_assets" in warning_types
    assert "inventory_growth_outpaced_assets" in warning_types
    assert "large_reported_movement" in warning_types


def test_analysis_context_states_empty_data_and_quality_limitations():
    analysis = calculate_analysis(7, [row(2024)])
    context = analysis_context(analysis, "Example Co", "EXAMPLE")

    assert "Company: Example Co (EXAMPLE)" in context
    assert "Fiscal years included: 2024" in context
    assert "total_assets: 2024=" not in context
    assert "Data-quality limitations:" in context

    empty = calculate_analysis(7, [])
    empty_context = analysis_context(empty, "Empty Co", "EMPTY")
    assert "Fiscal years included: none" in empty_context
    assert "- none" in empty_context
