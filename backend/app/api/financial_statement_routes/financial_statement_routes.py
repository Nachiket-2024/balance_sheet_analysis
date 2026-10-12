from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import BALANCE_SHEET_IMPORT, BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET
from ...access.scope import resource_scope_dict
from ...app_sdk import rate_limiter_service
from ...companies.company_crud import get_company_by_id
from ...financial_statements.financial_statement_crud import (
    YFinanceFetchError,
    get_statement,
    import_statement,
    list_statements,
)
from ...financial_statements.financial_statement_schema import FinancialStatementResponse, StatementType
from ...financial_statements.statement_analysis import calculate_statement_analysis
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/financial-statements", tags=["financial-statements"])


async def _authorized_company(company_id: int, action: str, current_user: dict, db: AsyncSession):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(
        current_user["email"], action, RESOURCE_BALANCE_SHEET, db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return company


@router.get("/company/{company_id}", response_model=list[FinancialStatementResponse])
async def list_company_financial_statements(
    company_id: int,
    statement_type: StatementType | None = Query(default=None),
    period_type: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorized_company(company_id, BALANCE_SHEET_READ, current_user, db)
    return await list_statements(company_id, statement_type, db, period_type=period_type)


@router.get("/company/{company_id}/analysis")
async def analyze_company_financial_statements(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorized_company(company_id, BALANCE_SHEET_READ, current_user, db)
    return calculate_statement_analysis(await list_statements(company_id, None, db))


@router.get("/{company_id}/{statement_type}/{year}", response_model=FinancialStatementResponse)
async def get_company_financial_statement(
    company_id: int,
    statement_type: StatementType,
    year: int,
    period_type: str = Query(default="annual"),
    period_number: int = Query(default=0, ge=0, le=4),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorized_company(company_id, BALANCE_SHEET_READ, current_user, db)
    return await get_or_404(
        get_statement(company_id, statement_type, year, db, period_type, period_number),
        "Financial statement not found",
        code="FINANCIAL_STATEMENT_NOT_FOUND",
    )


@router.post("/{company_id}/{statement_type}/{year}", response_model=FinancialStatementResponse, status_code=status.HTTP_201_CREATED)
@rate_limiter_service.rate_limited(
    "financial_statement_import", account_key_func=lambda kwargs: kwargs["current_user"]["email"]
)
async def import_company_financial_statement(
    request: Request,
    company_id: int,
    statement_type: StatementType,
    year: int,
    period_type: str = Query(default="annual"),
    period_number: int = Query(default=0, ge=0, le=4),
    refresh: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await _authorized_company(company_id, BALANCE_SHEET_IMPORT, current_user, db)
    try:
        return await import_statement(company_id, statement_type, year, company.ticker, db, refresh=refresh, period_type=period_type, period_number=period_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except YFinanceFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
