from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MetricStatus = Literal["available", "unavailable"]


class AnalysisMetric(BaseModel):
    value: float | None = None
    status: MetricStatus
    unit: str
    denominator: str | None = None
    source_fields: list[str] = Field(default_factory=list)
    note: str | None = None


class TrendPoint(BaseModel):
    year: int
    value: float | None = None
    yoy_change_pct: float | None = None
    status: MetricStatus
    unit: str
    source_fields: list[str] = Field(default_factory=list)


class SourceYear(BaseModel):
    year: int
    values: dict[str, float | None]


class DataQualityIssue(BaseModel):
    code: str
    severity: Literal["info", "warning"]
    year: int | None = None
    fields: list[str] = Field(default_factory=list)
    message: str


class AnalysisWarning(BaseModel):
    type: str
    severity: Literal["info", "review"]
    message: str
    years: list[int] = Field(default_factory=list)
    evidence: dict[str, float | int | str | None] = Field(default_factory=dict)


class BalanceSheetAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: int
    requested_years: list[int] | None = None
    fiscal_years: list[int]
    unit: str
    thresholds: dict[str, float | int]
    trends: dict[str, list[TrendPoint]]
    metrics: dict[str, list[AnalysisMetric]]
    composition: dict[str, list[AnalysisMetric]]
    source_values: list[SourceYear]
    warnings: list[AnalysisWarning]
    data_quality: list[DataQualityIssue]
    normalization: dict | None = None


class CurrencyRateCreate(BaseModel):
    source_currency: str = Field(min_length=3, max_length=8)
    target_currency: str = Field(min_length=3, max_length=8)
    effective_date: date
    rate: float = Field(gt=0)
    source: str = Field(min_length=1, max_length=128)
    source_url: str | None = Field(default=None, max_length=1024)


class CurrencyRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    source_currency: str
    target_currency: str
    effective_date: date
    rate: float
    source: str
    source_url: str | None


class CompanyAnalysisComparison(BaseModel):
    company_id: int
    company_name: str
    ticker: str
    analysis: BalanceSheetAnalysisResponse


class BalanceSheetComparisonResponse(BaseModel):
    companies: list[CompanyAnalysisComparison]


class BenchmarkPoint(BaseModel):
    company_id: int
    company_name: str
    ticker: str
    value: float | None
    percentile: float | None


class BenchmarkResponse(BaseModel):
    metric: str
    year: int | None
    unit: str
    points: list[BenchmarkPoint]


class AnalysisNotificationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: int
    enabled: bool
    recipients: list[str]
    minimum_severity: str
    escalation_after_hours: int
    escalation_recipients: list[str]


class AnalysisNotificationPolicyUpdate(BaseModel):
    enabled: bool | None = None
    recipients: list[str] | None = Field(default=None, max_length=50)
    minimum_severity: str | None = None
    escalation_after_hours: int | None = Field(default=None, ge=0, le=720)
    escalation_recipients: list[str] | None = Field(default=None, max_length=50)


class AnalysisNotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_email: str
    email_enabled: bool


class AnalysisNotificationPreferenceUpdate(BaseModel):
    email_enabled: bool


class AnalysisNotificationDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: int
    company_id: int
    channel: str
    recipient: str
    status: str
    job_id: int | None
    created_at: datetime


class AnalysisSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company_id: int
    thresholds: dict[str, float]
    target_currency: str | None = None
    display_scale: float = 1.0


class AnalysisSettingsUpdate(BaseModel):
    thresholds: dict[str, float] | None = None
    target_currency: str | None = Field(default=None, min_length=3, max_length=8)
    display_scale: float | None = Field(default=None, gt=0, le=1_000_000)


class AnalysisSettingsHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    changed_by: str
    thresholds: dict[str, float]
    target_currency: str | None
    display_scale: float
    created_at: datetime


class AnalysisAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    alert_key: str
    alert_type: str
    severity: str
    message: str
    years: list[int]
    evidence: dict
    status: str
    created_at: datetime
    last_seen_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class AnalysisAlertStatusUpdate(BaseModel):
    status: Literal["open", "acknowledged", "resolved"]
