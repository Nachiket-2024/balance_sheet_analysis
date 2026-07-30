from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import (
    BALANCE_SHEET_DELETE,
    BALANCE_SHEET_IMPORT,
    BALANCE_SHEET_READ,
    RESOURCE_BALANCE_SHEET,
)
from ...access.scope import resource_scope_dict
from ...app_sdk import rate_limiter_service
from ...balance_sheets.balance_sheet_crud import (
    YFinanceFetchError,
    get_balance_sheet,
    import_balance_sheet,
    list_balance_sheets_for_company,
)
from ...balance_sheets.balance_sheet_crud import (
    delete_balance_sheet as delete_balance_sheet_row,
)
from ...balance_sheets.balance_sheet_schema import BalanceSheetResponse
from ...companies.company_crud import get_company_by_id
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/balance-sheets", tags=["balance-sheets"])


@router.get("/company/{company_id}", response_model=list[BalanceSheetResponse])
async def list_company_balance_sheets(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """Every balance sheet on file for one company, across all fiscal
    years: "review the past multiple balance sheets quickly" from the
    problem statement. Access-checked against this specific company (a
    single resource, not a list to filter), unlike company_routes'
    list_companies, which filters across many companies at once."""
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        BALANCE_SHEET_READ,
        RESOURCE_BALANCE_SHEET,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return await list_balance_sheets_for_company(company_id, db)


@router.get("/{company_id}/{year}", response_model=BalanceSheetResponse)
async def get_company_balance_sheet(
    company_id: int,
    year: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        BALANCE_SHEET_READ,
        RESOURCE_BALANCE_SHEET,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return await get_or_404(get_balance_sheet(company_id, year, db), "Balance sheet not found")


@router.post("/{company_id}/{year}", response_model=BalanceSheetResponse, status_code=status.HTTP_201_CREATED)
@rate_limiter_service.rate_limited(
    "balance_sheet_import", account_key_func=lambda kwargs: kwargs["current_user"]["email"]
)
async def create_company_balance_sheet(
    request: Request,
    company_id: int,
    year: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """Imports one fiscal year's balance sheet from yfinance for this
    company's ticker. Analyst-only action (see access/permissions.py):
    top-management reads, analysts maintain the data.

    Rate-limited (per-IP and per-account) since each import is a real
    outbound call to yfinance; without this, one caller could hammer
    yfinance through this endpoint."""
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        BALANCE_SHEET_IMPORT,
        RESOURCE_BALANCE_SHEET,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    try:
        return await import_balance_sheet(company_id, year, company.ticker, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except YFinanceFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.delete("/{company_id}/{year}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_balance_sheet(
    company_id: int,
    year: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")
    await authorization_service.require(
        current_user["email"],
        BALANCE_SHEET_DELETE,
        RESOURCE_BALANCE_SHEET,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    balance_sheet = await get_or_404(get_balance_sheet(company_id, year, db), "Balance sheet not found")
    await delete_balance_sheet_row(balance_sheet, db)
