from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.current_user.current_user_dependency import get_current_user
from ....authorization.repositories.policy_repository import policy_repository
from ....authorization.schemas.policy_schema import PolicyRead, UserPoliciesRead
from ....database.connection import database

self_router = APIRouter(prefix="/authorization", tags=["Authorization"])


@self_router.get("/users/me/policies", response_model=UserPoliciesRead)
async def list_my_policies(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """Return the caller's policy assignments without requiring policies:read."""
    policies = await policy_repository.get_policies_for_user(current_user["email"], db)
    return UserPoliciesRead(
        user_email=current_user["email"],
        policies=[PolicyRead.model_validate(policy) for policy in policies],
    )
