from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    ticker: str = Field(min_length=1, max_length=32)
    parent_company_id: int | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    """
    All fields optional (PATCH semantics): a request only sends the fields
    it wants to change, unlike CompanyCreate where every field is required.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    ticker: str | None = Field(default=None, min_length=1, max_length=32)
    parent_company_id: int | None = None


class CompanyResponse(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_root_id: int
    created_at: datetime
    updated_at: datetime


class CompanyListItem(CompanyResponse):
    """CompanyResponse plus the parent's name, resolved by GET /companies/'s
    own join (see company_crud.py's list_companies_in_scope) instead of a
    lookup per row. Needed because CompaniesPage is now paginated (see its
    own comment on why): the table shows every row's parent by name, and can
    no longer resolve that itself from an already-fully-loaded company list."""

    parent_name: str | None = None


class CompanyStatsRead(BaseModel):
    total: int
    group_roots: int
    subsidiaries: int


class TickerLookupResponse(BaseModel):
    """`name` is None (not a 404) when yfinance has no company for `ticker`:
    a mistyped/delisted ticker is an expected outcome for this best-effort
    autofill lookup, not an error."""

    ticker: str
    name: str | None


class TickerSearchResult(BaseModel):
    ticker: str
    name: str
    exchange: str


class TickerSearchResponse(BaseModel):
    query: str
    results: list[TickerSearchResult]
