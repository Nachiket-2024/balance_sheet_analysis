from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import COMPANY_CREATE, COMPANY_DELETE, COMPANY_READ, RESOURCE_COMPANY
from ...access.scope import get_company_scope, resource_scope_dict
from ...companies.company_crud import create_company, delete_company, get_company_by_id, list_companies_in_scope
from ...companies.company_schema import CompanyCreate, CompanyResponse
from ...sdk import authorization_service, database, get_current_user, get_or_404, require_authorization

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Every company `current_user` may read, derived from their own assigned
    policies' conditions (see app/access/scope.py), not filtered client-side.
    A CEO's policy is scoped to their one company_id; a group executive's is
    scoped to their group_root_id; an unscoped policy (e.g. admin) sees all.
    """
    scope = await get_company_scope(current_user["email"], COMPANY_READ, RESOURCE_COMPANY, db)
    return await list_companies_in_scope(scope, db)


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


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found")

    # Resource-instance check: fetch first, then authorize against the
    # actual row, so a user scoped to company_id=5 gets 403 (not a leaked
    # 200) when asking for company_id=6, see access/scope.py's docstring
    # for why list endpoints (above) use get_company_scope instead of this.
    await authorization_service.require(
        current_user["email"],
        COMPANY_READ,
        RESOURCE_COMPANY,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return company


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
