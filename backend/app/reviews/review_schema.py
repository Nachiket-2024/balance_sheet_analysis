from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewStatus = Literal["draft", "reviewed", "approved", "superseded"]


class ReviewReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    years: list[int] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=10_000)


class ReviewReportStatusUpdate(BaseModel):
    status: ReviewStatus
    notes: str | None = Field(default=None, max_length=10_000)


class ReviewReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    created_by_email: str
    title: str
    status: ReviewStatus
    years: list[int]
    analysis: dict
    created_at: datetime
    updated_at: datetime
    notes: str | None


class ReviewCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class ReviewCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_report_id: int
    author_email: str
    body: str
    created_at: datetime


class ReviewAssignmentCreate(BaseModel):
    assigned_to_email: str = Field(min_length=3, max_length=320)


class ReviewAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_report_id: int
    assigned_to_email: str
    assigned_by_email: str
    created_at: datetime


class ReviewSignoffCreate(BaseModel):
    status: ReviewStatus
    note: str | None = Field(default=None, max_length=10_000)


class ReviewSignoffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    review_report_id: int
    actor_email: str
    status: ReviewStatus
    note: str | None
    created_at: datetime
