from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import BALANCE_SHEET_IMPORT, BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET
from ...access.scope import resource_scope_dict
from ...balance_sheets.analysis_models import (
    AnalysisAlert,
    AnalysisNotificationDelivery,
    AnalysisSettingsHistory,
)
from ...balance_sheets.analysis_notifications import get_or_create_policy, get_or_create_preference, validate_policy
from ...balance_sheets.analysis_schema import (
    AnalysisAlertResponse,
    AnalysisAlertStatusUpdate,
    AnalysisNotificationDeliveryResponse,
    AnalysisNotificationPolicyResponse,
    AnalysisNotificationPolicyUpdate,
    AnalysisNotificationPreferenceResponse,
    AnalysisNotificationPreferenceUpdate,
    AnalysisSettingsHistoryResponse,
    AnalysisSettingsResponse,
    AnalysisSettingsUpdate,
    BalanceSheetAnalysisResponse,
    BalanceSheetComparisonResponse,
    BenchmarkPoint,
    BenchmarkResponse,
    CompanyAnalysisComparison,
    CurrencyRateCreate,
    CurrencyRateResponse,
)
from ...balance_sheets.analysis_service import _TREND_FIELDS, calculate_analysis
from ...balance_sheets.analysis_settings import (
    effective_thresholds,
    get_or_create_settings,
    sync_analysis_alerts,
    validate_thresholds,
)
from ...balance_sheets.balance_sheet_crud import list_balance_sheets_for_company_years
from ...balance_sheets.currency_model import CurrencyRate
from ...balance_sheets.currency_service import list_currency_rates, normalize_rows
from ...companies.company_crud import get_company_by_id
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/balance-sheet-analysis", tags=["balance-sheet-analysis"])


@router.get("/notifications/preferences", response_model=AnalysisNotificationPreferenceResponse)
async def get_analysis_notification_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    return await get_or_create_preference(current_user["email"], db)


@router.patch("/notifications/preferences", response_model=AnalysisNotificationPreferenceResponse)
async def update_analysis_notification_preferences(
    payload: AnalysisNotificationPreferenceUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    preference = await get_or_create_preference(current_user["email"], db)
    preference.email_enabled = payload.email_enabled
    await db.commit()
    await db.refresh(preference)
    return preference


@router.get("/benchmark", response_model=BenchmarkResponse)
async def benchmark_company_balance_sheet_analysis(
    company_ids: list[int] = Query(..., min_length=2, max_length=20),
    metric: str = Query(default="total_assets"),
    year: int | None = Query(default=None),
    target_currency: str | None = Query(default=None, min_length=3, max_length=8),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    if metric not in _TREND_FIELDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported benchmark metric")
    if len(set(company_ids)) != len(company_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_ids must not contain duplicates")
    raw_points: list[tuple[int, str, str, float | None]] = []
    unit = "reported currency units"
    for company_id in company_ids:
        company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
        await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
        rows = await list_balance_sheets_for_company_years(company.id, [year] if year else None, db)
        settings = await get_or_create_settings(company.id, db)
        currency = (target_currency or settings.target_currency or "").upper() or None
        if currency:
            rows, _ = normalize_rows(rows, currency, await list_currency_rates(company.id, db), settings.display_scale)
            unit = f"{currency} units / {settings.display_scale:g}"
        analysis = calculate_analysis(company.id, rows, [year] if year else None, settings.thresholds)
        selected_year = year or (analysis.fiscal_years[-1] if analysis.fiscal_years else None)
        point = next((item for item in analysis.trends[metric] if item.year == selected_year), None)
        raw_points.append((company.id, company.name, company.ticker, point.value if point else None))
    values = [item[3] for item in raw_points if item[3] is not None]
    points = []
    for company_id, company_name, ticker, value in raw_points:
        percentile = None if value is None or not values else round(sum(item < value for item in values) / len(values) * 100, 2)
        points.append(BenchmarkPoint(company_id=company_id, company_name=company_name, ticker=ticker, value=value, percentile=percentile))
    return BenchmarkResponse(metric=metric, year=year, unit=unit, points=points)


@router.get("/compare", response_model=BalanceSheetComparisonResponse)
async def compare_company_balance_sheet_analysis(
    company_ids: list[int] = Query(..., min_length=1, max_length=20),
    years: list[int] | None = Query(default=None, description="Fiscal years to compare for every selected company."),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """Compare explicitly selected companies without client-side filtering."""
    if len(set(company_ids)) != len(company_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="company_ids must not contain duplicates")
    comparisons: list[CompanyAnalysisComparison] = []
    for company_id in company_ids:
        company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
        await authorization_service.require(
            current_user["email"],
            BALANCE_SHEET_READ,
            RESOURCE_BALANCE_SHEET,
            db,
            resource=resource_scope_dict(company.id, company.group_root_id),
        )
        rows = await list_balance_sheets_for_company_years(company.id, years, db)
        settings = await get_or_create_settings(company.id, db)
        comparisons.append(
            CompanyAnalysisComparison(
                company_id=company.id,
                company_name=company.name,
                ticker=company.ticker,
                analysis=calculate_analysis(company.id, rows, years, settings.thresholds),
            )
        )
    return BalanceSheetComparisonResponse(companies=comparisons)


@router.get("/company/{company_id}", response_model=BalanceSheetAnalysisResponse)
async def get_company_balance_sheet_analysis(
    company_id: int,
    years: list[int] | None = Query(default=None, description="Fiscal years to compare; omitted means every year on file."),
    target_currency: str | None = Query(default=None, min_length=3, max_length=8),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(
        current_user["email"],
        BALANCE_SHEET_READ,
        RESOURCE_BALANCE_SHEET,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    rows = await list_balance_sheets_for_company_years(company.id, years, db)
    settings = await get_or_create_settings(company.id, db)
    requested_currency = (target_currency or settings.target_currency or "").upper() or None
    normalization = None
    if requested_currency:
        rows, normalization = normalize_rows(rows, requested_currency, await list_currency_rates(company.id, db), settings.display_scale)
    analysis = calculate_analysis(company.id, rows, years, settings.thresholds)
    analysis.normalization = normalization
    if normalization:
        analysis.unit = f"{normalization['target_currency']} units / {normalization['display_scale']:g}"
    await sync_analysis_alerts(company.id, analysis.warnings, db)
    return analysis


@router.get("/company/{company_id}/settings", response_model=AnalysisSettingsResponse)
async def get_company_analysis_settings(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    settings = await get_or_create_settings(company_id, db)
    return AnalysisSettingsResponse(company_id=company_id, thresholds={key: float(value) for key, value in effective_thresholds(settings).items()}, target_currency=settings.target_currency, display_scale=settings.display_scale)


@router.get("/company/{company_id}/currency-rates", response_model=list[CurrencyRateResponse])
async def get_company_currency_rates(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    return await list_currency_rates(company_id, db)


@router.post("/company/{company_id}/currency-rates", response_model=CurrencyRateResponse, status_code=status.HTTP_201_CREATED)
async def add_company_currency_rate(
    company_id: int,
    payload: CurrencyRateCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_IMPORT, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    if payload.source_currency.upper() == payload.target_currency.upper():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and target currencies must differ")
    rate = CurrencyRate(company_id=company_id, source_currency=payload.source_currency.upper(), target_currency=payload.target_currency.upper(), effective_date=payload.effective_date, rate=payload.rate, source=payload.source, source_url=payload.source_url)
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return rate


@router.patch("/company/{company_id}/settings", response_model=AnalysisSettingsResponse)
async def update_company_analysis_settings(
    company_id: int,
    payload: AnalysisSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_IMPORT, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    settings = await get_or_create_settings(company_id, db)
    if payload.thresholds is not None:
        try:
            settings.thresholds = validate_thresholds(payload.thresholds)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if payload.target_currency is not None:
        settings.target_currency = payload.target_currency.upper()
    if payload.display_scale is not None:
        settings.display_scale = payload.display_scale
    db.add(AnalysisSettingsHistory(company_id=company_id, changed_by=current_user["email"], thresholds={key: float(value) for key, value in effective_thresholds(settings).items()}, target_currency=settings.target_currency, display_scale=settings.display_scale))
    await db.commit()
    await db.refresh(settings)
    return AnalysisSettingsResponse(company_id=company_id, thresholds={key: float(value) for key, value in effective_thresholds(settings).items()}, target_currency=settings.target_currency, display_scale=settings.display_scale)


@router.get("/company/{company_id}/settings/history", response_model=list[AnalysisSettingsHistoryResponse])
async def get_company_analysis_settings_history(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    result = await db.execute(select(AnalysisSettingsHistory).where(AnalysisSettingsHistory.company_id == company_id).order_by(AnalysisSettingsHistory.created_at.desc()))
    return list(result.scalars().all())


@router.get("/company/{company_id}/alerts", response_model=list[AnalysisAlertResponse])
async def list_company_analysis_alerts(
    company_id: int,
    include_resolved: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    query = select(AnalysisAlert).where(AnalysisAlert.company_id == company_id)
    if not include_resolved:
        query = query.where(AnalysisAlert.status != "resolved")
    result = await db.execute(query.order_by(AnalysisAlert.last_seen_at.desc()))
    return list(result.scalars().all())


@router.get("/company/{company_id}/notification-policy", response_model=AnalysisNotificationPolicyResponse)
async def get_company_analysis_notification_policy(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    return await get_or_create_policy(company_id, db)


@router.patch("/company/{company_id}/notification-policy", response_model=AnalysisNotificationPolicyResponse)
async def update_company_analysis_notification_policy(
    company_id: int,
    payload: AnalysisNotificationPolicyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_IMPORT, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    policy = await get_or_create_policy(company_id, db)
    recipients = payload.recipients if payload.recipients is not None else policy.recipients
    minimum_severity = payload.minimum_severity if payload.minimum_severity is not None else policy.minimum_severity
    escalation_after_hours = payload.escalation_after_hours if payload.escalation_after_hours is not None else policy.escalation_after_hours
    escalation_recipients = payload.escalation_recipients if payload.escalation_recipients is not None else policy.escalation_recipients
    try:
        normalized = validate_policy(
            recipients=recipients,
            minimum_severity=minimum_severity,
            escalation_after_hours=escalation_after_hours,
            escalation_recipients=escalation_recipients,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    policy.enabled = payload.enabled if payload.enabled is not None else policy.enabled
    policy.recipients = normalized["recipients"]
    policy.minimum_severity = normalized["minimum_severity"]
    policy.escalation_after_hours = normalized["escalation_after_hours"]
    policy.escalation_recipients = normalized["escalation_recipients"]
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("/company/{company_id}/notification-deliveries", response_model=list[AnalysisNotificationDeliveryResponse])
async def list_company_analysis_notification_deliveries(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    result = await db.execute(
        select(AnalysisNotificationDelivery)
        .where(AnalysisNotificationDelivery.company_id == company_id)
        .order_by(AnalysisNotificationDelivery.created_at.desc())
        .limit(200)
    )
    return list(result.scalars().all())


@router.patch("/alerts/{alert_id}", response_model=AnalysisAlertResponse)
async def update_analysis_alert(
    alert_id: int,
    payload: AnalysisAlertStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    alert = await get_or_404(db.get(AnalysisAlert, alert_id), "Alert not found", code="ALERT_NOT_FOUND")
    company = await get_or_404(get_company_by_id(alert.company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db, resource=resource_scope_dict(company.id, company.group_root_id))
    alert.status = payload.status
    if payload.status == "acknowledged":
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = current_user["email"]
    await db.commit()
    await db.refresh(alert)
    return alert
