import asyncio
from typing import Literal

import yfinance as yf
from curl_cffi import requests as curl_requests
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased

from ..access.scope import CompanyScope
from .company_model import Company
from .company_schema import CompanyCreate, CompanyUpdate

# Allowlisted sort keys, same rationale as mystic_auth's _SORTABLE_COLUMN_NAMES.
# "parent" is handled separately because it sorts on the joined parent's name.
_SORTABLE_COLUMN_NAMES = {"name", "ticker", "created_at"}

HierarchyScope = Literal["root", "subsidiary"]

# Same timeout/impersonation reasoning as balance_sheet_crud.py's own
# _YFINANCE_TIMEOUT_SECONDS: yfinance has no built-in timeout and requires a
# curl_cffi session with browser impersonation or Yahoo blocks the request.
_YFINANCE_TIMEOUT_SECONDS = 15


class TickerLookupError(RuntimeError):
    """A yfinance/network failure while looking up a ticker's company name,
    distinct from "no company found for this ticker" (a plain None return,
    e.g. a typo'd or delisted ticker, not a failure worth a 502)."""


def _lookup_company_name_by_ticker_sync(ticker: str) -> str | None:
    """Blocking network call (yfinance has no async API); always run this via
    asyncio.to_thread. Best-effort autofill helper for the company-create
    form: not part of create_company itself, so a slow/failed yfinance
    response never blocks actually creating the company."""
    try:
        session: curl_requests.Session = curl_requests.Session(
            impersonate="chrome", timeout=_YFINANCE_TIMEOUT_SECONDS
        )
        info = yf.Ticker(ticker, session=session).info
    except Exception as exc:
        raise TickerLookupError(f"Failed to look up ticker '{ticker}' from yfinance: {exc}") from exc

    return info.get("longName") or info.get("shortName")


async def lookup_company_name_by_ticker(ticker: str) -> str | None:
    return await asyncio.to_thread(_lookup_company_name_by_ticker_sync, ticker)


_TICKER_SEARCH_MAX_RESULTS = 8


def _search_company_tickers_sync(query: str) -> list[dict[str, str]]:
    """Blocking network call, same asyncio.to_thread rule as the lookup
    above. Uses yfinance's Search (Yahoo's autocomplete endpoint) rather
    than the single-ticker Ticker().info call: it's built for prefix/fuzzy
    matching against name or ticker, e.g. "REL" -> RELIANCE.NS, RS, etc."""
    try:
        session: curl_requests.Session = curl_requests.Session(
            impersonate="chrome", timeout=_YFINANCE_TIMEOUT_SECONDS
        )
        quotes = yf.Search(query, max_results=_TICKER_SEARCH_MAX_RESULTS, session=session).quotes
    except Exception as exc:
        raise TickerLookupError(f"Failed to search tickers for '{query}' from yfinance: {exc}") from exc

    results = []
    for quote in quotes:
        symbol = quote.get("symbol")
        name = quote.get("longname") or quote.get("shortname")
        if not symbol or not name:
            continue
        results.append({"ticker": symbol, "name": name, "exchange": quote.get("exchDisp") or quote.get("exchange") or ""})
    return results


async def search_company_tickers(query: str) -> list[dict[str, str]]:
    return await asyncio.to_thread(_search_company_tickers_sync, query)


async def create_company(data: CompanyCreate, db: AsyncSession) -> Company:
    """
    Inserts a Company, then resolves group_root_id: a root company's
    group_root_id is its own id (only known after insert); a child's is
    simply its parent's group_root_id (already resolved, since a parent must
    already exist to be referenced), so no recursive walk is needed either way.
    See company_model.py's docstring for why group_root_id exists at all.

    Raises ValueError (translated to HTTP 400 by the route layer) if
    parent_company_id doesn't exist, or if `ticker` is already taken:
    tickers are unique (see company_model.py), and two concurrent requests
    for the same new ticker can both pass validation before either commits.
    """
    parent = None
    if data.parent_company_id is not None:
        parent = await db.get(Company, data.parent_company_id)
        if parent is None:
            raise ValueError(f"parent_company_id {data.parent_company_id} does not exist")

    company = Company(
        name=data.name,
        ticker=data.ticker,
        parent_company_id=data.parent_company_id,
        group_root_id=0,  # placeholder until we have this row's own id
    )
    db.add(company)

    try:
        # The unique-ticker constraint violation surfaces as soon as the
        # INSERT is actually emitted, at flush(), not commit(), so both
        # must be inside this try, not just commit() (a bug an earlier
        # version of this function had: the except below never fired
        # because flush() alone already raised, unguarded).
        await db.flush()  # assigns company.id without ending the transaction
        company.group_root_id = parent.group_root_id if parent is not None else company.id
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError(f"A company with ticker '{data.ticker}' already exists") from exc
    await db.refresh(company)
    return company


async def update_company(company: Company, data: CompanyUpdate, db: AsyncSession) -> Company:
    """
    Same group_root_id re-resolution as create_company (see its docstring):
    only recomputed when parent_company_id is actually part of this request,
    since re-walking it unconditionally on every field-only-rename would
    otherwise risk clobbering a correct value with a stale read.

    Raises ValueError (translated to HTTP 400 by the route layer) for the
    same reasons create_company does, plus: a company can't be set as its
    own parent (create_company doesn't need this guard, since a brand-new
    row has no id yet to reference), and a company with subsidiaries can't
    be reparented at all. Same reasoning as delete_company's subsidiary
    guard: reparenting would leave every subsidiary's group_root_id pointing
    at a group this company no longer roots, and unlike delete there's no
    ON DELETE SET NULL to fall back on here.
    """
    fields = data.model_dump(exclude_unset=True)

    if "parent_company_id" in fields and fields["parent_company_id"] != company.parent_company_id:
        new_parent_id = fields["parent_company_id"]
        if new_parent_id == company.id:
            raise ValueError("A company cannot be its own parent")
        subsidiary_count = await db.scalar(
            select(func.count()).select_from(Company).where(Company.parent_company_id == company.id)
        )
        if subsidiary_count:
            raise ValueError(
                f"Cannot reparent '{company.name}': it has {subsidiary_count} subsidiary company(ies), "
                "whose group_root_id would then be left pointing at the wrong group."
            )
        if new_parent_id is None:
            company.group_root_id = company.id
        else:
            parent = await db.get(Company, new_parent_id)
            if parent is None:
                raise ValueError(f"parent_company_id {new_parent_id} does not exist")
            company.group_root_id = parent.group_root_id
        company.parent_company_id = new_parent_id

    if "name" in fields:
        company.name = fields["name"]
    if "ticker" in fields:
        company.ticker = fields["ticker"]

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError(f"A company with ticker '{fields.get('ticker')}' already exists") from exc
    await db.refresh(company)
    return company


async def delete_company(company: Company, db: AsyncSession) -> None:
    """
    Raises ValueError (translated to HTTP 400 by the route layer) if `company`
    has subsidiaries. company_model.py's parent_company_id FK is ON DELETE
    SET NULL, not CASCADE, so deleting a parent would otherwise just null out
    each child's parent_company_id while leaving group_root_id pointing at
    the now-deleted row (group_root_id has no FK of its own, see the model's
    docstring for why): a group-scoped policy would then silently stop
    matching companies that still exist. Deleting the subsidiaries first
    (which walks group_root_id back to a still-valid root, or removes the
    whole group) avoids ever producing that dangling reference. Balance
    sheets don't have this problem: BalanceSheet.company_id is ON DELETE
    CASCADE, so they're removed automatically.

    This check isn't atomic with the delete below (unlike create_company's
    ticker-uniqueness race, there's no DB constraint to catch it): a
    subsidiary created between the count and the delete would still slip
    through. Narrow, admin-only window, not guarded against further.
    """
    subsidiary_count = await db.scalar(
        select(func.count()).select_from(Company).where(Company.parent_company_id == company.id)
    )
    if subsidiary_count:
        raise ValueError(
            f"Cannot delete '{company.name}': it has {subsidiary_count} subsidiary company(ies). "
            "Delete or reassign those first."
        )
    await db.delete(company)
    await db.commit()


async def get_company_by_id(company_id: int, db: AsyncSession) -> Company | None:
    return await db.get(Company, company_id)


async def get_company_by_ticker(ticker: str, db: AsyncSession) -> Company | None:
    result = await db.execute(select(Company).where(Company.ticker == ticker))
    return result.scalar_one_or_none()


def _hierarchy_filter(hierarchy_scope: HierarchyScope | None):
    """"root": companies with no parent. "subsidiary": companies with one.
    Unset: no filter, same "root"/"subsidiary" split CompaniesPage's scope
    select and CompanyStatsCard's tiles use."""
    if hierarchy_scope == "root":
        return Company.parent_company_id.is_(None)
    if hierarchy_scope == "subsidiary":
        return Company.parent_company_id.isnot(None)
    return None


def _apply_scope_and_filters(
    stmt,
    scope: CompanyScope,
    search: str | None,
    hierarchy_scope: HierarchyScope | None,
):
    if not scope.unrestricted:
        clauses = []
        if scope.company_ids:
            clauses.append(Company.id.in_(scope.company_ids))
        if scope.group_root_ids:
            clauses.append(Company.group_root_id.in_(scope.group_root_ids))
        stmt = stmt.where(or_(*clauses))

    if search:
        # Server-side search is required because the paginated UI no longer
        # has every scoped company loaded client-side.
        pattern = f"%{search}%"
        stmt = stmt.where(or_(Company.name.ilike(pattern), Company.ticker.ilike(pattern)))

    hierarchy_clause = _hierarchy_filter(hierarchy_scope)
    if hierarchy_clause is not None:
        stmt = stmt.where(hierarchy_clause)

    return stmt


async def list_companies_in_scope(
    scope: CompanyScope,
    db: AsyncSession,
    *,
    limit: int = 1000,
    offset: int = 0,
    search: str | None = None,
    hierarchy_scope: HierarchyScope | None = None,
    sort_by: str | None = None,
    sort_dir: str = "asc",
) -> list[tuple[Company, str | None]]:
    """
    The companies `scope` (see app/access/scope.py) grants access to,
    paginated and optionally filtered/sorted. An empty scope short-circuits
    to no query at all, since the caller already knows the answer is
    "nothing".

    Returns (company, parent_name) pairs. parent_name comes from a self-join
    rather than one lookup per row, which also enables server-side parent sort.
    """
    if scope.is_empty():
        return []

    parent = aliased(Company)
    stmt = select(Company, parent.name).outerjoin(parent, Company.parent_company_id == parent.id)
    stmt = _apply_scope_and_filters(stmt, scope, search, hierarchy_scope)

    order_column: InstrumentedAttribute
    if sort_by == "parent":
        order_column = parent.name
    elif sort_by in _SORTABLE_COLUMN_NAMES:
        order_column = getattr(Company, sort_by)
    else:
        order_column = Company.id
    direction = asc if sort_dir == "asc" else desc
    # id as a secondary key for stable ordering, same as mystic_auth's own
    # UserBaseCRUD._order_by.
    stmt = stmt.order_by(direction(order_column), direction(Company.id)).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def count_companies_in_scope(
    scope: CompanyScope,
    db: AsyncSession,
    *,
    search: str | None = None,
    hierarchy_scope: HierarchyScope | None = None,
) -> int:
    """Total matching rows, ignoring limit/offset. Lets a caller compute how
    many pages exist (GET /companies/'s X-Total-Count header) or build
    CompanyStatsCard's aggregate counts (GET /companies/stats)."""
    if scope.is_empty():
        return 0

    stmt = _apply_scope_and_filters(select(func.count()).select_from(Company), scope, search, hierarchy_scope)
    return await db.scalar(stmt)
