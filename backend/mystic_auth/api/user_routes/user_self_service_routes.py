from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.password_logic.password_service import password_service
from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...auth.token_logic.jwt_service import jwt_service
from ...auth.token_logic.token_cookie_handler import token_cookie_handler
from ...auth.token_logic.token_schema import TokenPairResponseSchema
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...core.errors import AppError
from ...database.connection import database
from ...user_crud.user_crud_collector import user_crud
from ...user_crud.user_crud_modules.user_update_payload_preparation import prepare_update_data
from ...user_session.session_service import session_service
from ...user_table.user_schema import UserRead, UserUpdate
from ..get_or_404.get_or_404 import get_or_404

# Split from the combined user_routes.py: this file is exactly the two
# self-service endpoints (a caller acting on their own account), so it's
# never gated by anything beyond users:read_own/update_own, unlike every
# route in user_management_routes.py. Kept as its own router (rather than
# folded into that one) so the two permission tiers can never accidentally
# share a route by being defined in the same file, mirroring pbac_routes/'s
# split by concern (policy_crud_routes.py, policy_assignment_routes.py, etc.).
router = APIRouter(prefix="/users", tags=["Users"])

_RESOURCE_TYPE = "users"


@router.get("/me", response_model=UserRead)
async def get_my_profile(
    current_user: dict = Depends(require_authorization(Permission.USERS_READ_OWN.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session)
):
    email = current_user["email"]
    user = await get_or_404(user_crud.get_by_email(email, db), "User not found", code="USER_NOT_FOUND")
    return user


@router.put("/me", response_model=UserRead)
async def update_my_profile(
    update_data: UserUpdate,
    response: Response,
    current_user: dict = Depends(require_authorization(Permission.USERS_UPDATE_OWN.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session),
    access_token: str = Cookie(None),
):
    email = current_user["email"]
    user = await get_or_404(user_crud.get_by_email(email, db), "User not found", code="USER_NOT_FOUND")

    # A stolen access-token cookie (e.g. via XSS) is otherwise enough to
    # permanently lock the legitimate owner out by just setting a new
    # password: no proof of the old one required. Skipped for an
    # OAuth-only account (hashed_password is None) setting a password for
    # the first time, since there's nothing yet to confirm against.
    if update_data.password is not None and user.hashed_password is not None:
        if not update_data.current_password or not await password_service.verify_password(
            update_data.current_password, user.hashed_password
        ):
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CURRENT_PASSWORD_INCORRECT",
                detail="Current password is incorrect",
            )
        # Match password reset behavior: no-op password changes should not
        # succeed or revoke sessions.
        if await password_service.verify_password(update_data.password, user.hashed_password):
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="PASSWORD_MUST_DIFFER_FROM_CURRENT",
                detail="New password must be different from the current password",
            )

    prepared_data = await prepare_update_data(update_data)
    updated_user = await user_crud.update(db_obj=user, update_data=prepared_data, db=db)

    # Password changes revoke other sessions because old credentials may be
    # compromised. Keep the current chain because it supplied the current
    # password, then reissue tokens so it survives the account-version bump.
    if "hashed_password" in prepared_data:
        current_payload = await jwt_service.decode_payload(access_token) if access_token else None
        chain_id = current_payload.get("chain") if current_payload else None

        if chain_id:
            await refresh_token_service.revoke_all_tokens_for_user_except_chain(email, chain_id, db)

            new_access_token = await jwt_service.create_access_token(email, chain_id)
            new_refresh_token = await jwt_service.create_refresh_token(email, chain_id)
            token_cookie_handler.set_tokens_in_cookies(
                response,
                TokenPairResponseSchema(access_token=new_access_token, refresh_token=new_refresh_token),
            )

            # Keep Manage Sessions in sync without changing create_refresh_token's API.
            new_refresh_payload = await jwt_service.decode_payload(new_refresh_token)
            if new_refresh_payload and new_refresh_payload.get("jti") and new_refresh_payload.get("exp"):
                await session_service.rotate_session_by_chain(
                    db, chain_id, new_refresh_payload["jti"], new_refresh_payload["exp"], email=email
                )
        else:
            # Authorization should already have read this cookie. If the chain
            # is still unavailable, revoke the whole account instead.
            await refresh_token_service.revoke_all_tokens_for_user(email, db)

    return updated_user
