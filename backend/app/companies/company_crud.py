from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..access.scope import CompanyScope
from .company_model import Company
from .company_schema import CompanyCreate


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


async def list_companies_in_scope(scope: CompanyScope, db: AsyncSession) -> list[Company]:
    """
    The companies `scope` (see app/access/scope.py) grants access to. An
    empty scope short-circuits to no query at all, since the caller already knows
    the answer is "nothing".
    """
    if scope.is_empty():
        return []

    stmt = select(Company)
    if not scope.unrestricted:
        clauses = []
        if scope.company_ids:
            clauses.append(Company.id.in_(scope.company_ids))
        if scope.group_root_ids:
            clauses.append(Company.group_root_id.in_(scope.group_root_ids))
        stmt = stmt.where(or_(*clauses))

    result = await db.execute(stmt.order_by(Company.id))
    return list(result.scalars().all())
