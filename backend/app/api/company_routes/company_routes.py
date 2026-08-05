import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import COMPANY_CREATE, COMPANY_DELETE, COMPANY_READ, COMPANY_UPDATE, RESOURCE_COMPANY
from ...access.scope import get_company_scope, resource_scope_dict
from ...app_sdk import rate_limiter_service
from ...companies.company_crud import (
    HierarchyScope,
    TickerLookupError,
    count_companies_in_scope,
    create_company,
    delete_company,
    get_company_by_id,
    list_companies_in_scope,
    lookup_company_name_by_ticker,
    search_company_tickers,
    update_company,
)
from ...companies.company_schema import (
    CompanyCreate,
    CompanyListItem,
    CompanyResponse,
    CompanyStatsRead,
    CompanyUpdate,
    TickerLookupResponse,
    TickerSearchResponse,
)
from ...sdk import authorization_service, database, get_current_user, get_or_404, require_authorization

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyListItem])
async def list_companies(
    response: Response,
    # Keep the historical "all companies" default for API callers. The
    # frontend passes its own explicit limit and offset (see
    # companyQueries.ts), same convention as mystic_auth's own
    # GET /users/list_all_users.
    limit: int = Query(default=1000, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, description="Case-insensitive substring match on name or ticker"),
    hierarchy: HierarchyScope | None = Query(
        default=None,
        description="root: companies with no parent. subsidiary: companies with a parent. Unset: both.",
    ),
    sort_by: str | None = Query(
        default=None,
        description="Column to sort by: name, ticker, parent, or created_at. "
        "Any other value (including unset) falls back to id.",
    ),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Every company `current_user` may read, derived from their own assigned
    policies' conditions (see app/access/scope.py), not filtered client-side.
    A CEO's policy is scoped to their one company_id; a group executive's is
    scoped to their group_root_id; an unscoped policy (e.g. admin) sees all.

    X-Total-Count (not part of the response body) mirrors mystic_auth's own
    GET /users/ pagination convention, so CompaniesPage can render numbered
    pages without a second round trip.
    """
    scope = await get_company_scope(current_user["email"], COMPANY_READ, RESOURCE_COMPANY, db)
    total = await count_companies_in_scope(scope, db, search=search, hierarchy_scope=hierarchy)
    response.headers["X-Total-Count"] = str(total)
    rows = await list_companies_in_scope(
        scope,
        db,
        limit=limit,
        offset=offset,
        search=search,
        hierarchy_scope=hierarchy,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return [
        CompanyListItem(**CompanyResponse.model_validate(company).model_dump(), parent_name=parent_name)
        for company, parent_name in rows
    ]


@router.get("/stats", response_model=CompanyStatsRead)
async def get_company_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Same scope as the list itself (get_company_scope, not a separate
    permission): counts are of whatever this user is permitted to see, not a
    system-wide total. Mirrors mystic_auth's own GET /users/stats with three
    independent counts, run concurrently rather than awaited one at a time.
    Registered ahead of GET /{company_id} below: route order matters here,
    an unparameterized "/stats" must be matched before the "/{company_id}"
    path can try (and fail) to parse "stats" as an int.
    """
    scope = await get_company_scope(current_user["email"], COMPANY_READ, RESOURCE_COMPANY, db)
    total, group_roots, subsidiaries = await asyncio.gather(
        count_companies_in_scope(scope, db),
        count_companies_in_scope(scope, db, hierarchy_scope="root"),
        count_companies_in_scope(scope, db, hierarchy_scope="subsidiary"),
    )
    return CompanyStatsRead(total=total, group_roots=group_roots, subsidiaries=subsidiaries)


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def add_company(
    data: CompanyCreate,
    current_user: dict = Depends(require_authorization(COMPANY_CREATE, RESOURCE_COMPANY)),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Creating a company isn't scoped to an existing resource (there's nothing
    to check `resource_attributes` against yet), so the coarse
    require_authorization dependency is enough here, unlike the
    resource-scoped GET below.
    """
    try:
        return await create_company(data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/lookup/{ticker}", response_model=TickerLookupResponse)
@rate_limiter_service.rate_limited(
    "company_ticker_lookup", account_key_func=lambda kwargs: kwargs["current_user"]["email"]
)
async def lookup_company_ticker(
    request: Request,
    ticker: str,
    current_user: dict = Depends(require_authorization(COMPANY_CREATE, RESOURCE_COMPANY)),
):
    """
    Best-effort autofill for the "add company" form: given a ticker, looks up
    its company name from yfinance so the caller doesn't have to type it by
    hand. Gated by COMPANY_CREATE (not COMPANY_READ) since this is only ever
    useful as part of creating a company, and a real outbound yfinance call
    per keystroke-adjacent request is exactly what BALANCE_SHEET_IMPORT's own
    rate limit exists to prevent for the same reason (see balance_sheet_routes.py).
    """
    try:
        name = await lookup_company_name_by_ticker(ticker)
    except TickerLookupError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return TickerLookupResponse(ticker=ticker, name=name)


@router.get("/search/{query}", response_model=TickerSearchResponse)
@rate_limiter_service.rate_limited(
    "company_ticker_search", account_key_func=lambda kwargs: kwargs["current_user"]["email"]
)
async def search_tickers(
    request: Request,
    query: str,
    current_user: dict = Depends(require_authorization(COMPANY_CREATE, RESOURCE_COMPANY)),
):
    """
    Autocomplete-style search for the "add company" form's ticker field:
    given a partial ticker or name, returns candidate real-world
    ticker/name/exchange matches from yfinance's own search (distinct from
    the exact-match lookup above). Same gating and rate-limit reasoning as
    lookup_company_ticker, since this is called once per keystroke-adjacent
    request too.
    """
    try:
        results = await search_company_tickers(query)
    except TickerLookupError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return TickerSearchResponse(query=query, results=results)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")

    # Fetch first, then authorize against the actual row so an out-of-scope
    # existing company returns 403 instead of a leaked 200.
    await authorization_service.require(
        current_user["email"],
        COMPANY_READ,
        RESOURCE_COMPANY,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
async def edit_company(
    company_id: int,
    data: CompanyUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        COMPANY_UPDATE,
        RESOURCE_COMPANY,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    try:
        return await update_company(company, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        COMPANY_DELETE,
        RESOURCE_COMPANY,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    try:
        await delete_company(company, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
