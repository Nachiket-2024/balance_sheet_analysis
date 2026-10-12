from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    company_id: int
    years: list[int] | None = None  # None = use every fiscal year on file for this company
    # Bounded so one request can't build an unbounded-cost prompt against the
    # Groq API, generous enough for any realistic analyst question.
    question: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str


class ChatFeedback(BaseModel):
    helpful: bool
    comment: str | None = Field(default=None, max_length=2000)


class LLMUsageSummary(BaseModel):
    provider: str
    model: str
    daily_character_budget: int
    characters_used: int
    requests: int


class LLMProviderStatus(BaseModel):
    provider: str
    model: str
    configured: bool
    reachable: bool = False
    latency_ms: float | None = None
    checked_at: datetime | None = None
    error_code: str | None = None


class LLMAdminUsageEntry(BaseModel):
    user_email: str
    requests: int
    characters_used: int
    failed_requests: int


class LLMAdminUsageSummary(BaseModel):
    provider: str
    model: str
    since: datetime
    total_requests: int
    total_characters: int
    failed_requests: int
    users: list[LLMAdminUsageEntry]


class LLMProviderOperationsSummary(BaseModel):
    provider: str
    model: str
    since: datetime
    probes: int
    reachable_probes: int
    failed_probes: int
    average_latency_ms: float | None
    last_checked_at: datetime | None
    last_error_code: str | None
