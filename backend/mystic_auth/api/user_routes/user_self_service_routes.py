from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.password_logic.password_service import password_service
from ...auth.refresh_token_logic.refresh_token_service import refresh_token_service
from ...auth.security.rate_limiting.rate_limiter_service import rate_limiter_service
from ...auth.token_logic.jwt_service import jwt_service
from ...auth.token_logic.token_cookie_handler import token_cookie_handler
from ...auth.token_logic.token_schema import TokenPairResponseSchema
from ...auth.token_logic.token_version_store import TokenVersionUnavailableError
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...core.errors import AppError
from ...database.connection import database
from ...logging.logging_config import get_logger
from ...user.user_crud_collector import user_crud
from ...user.user_crud_modules.user_update_payload_preparation import prepare_update_data

# UserRole is only used for the system-account guard on self-delete, same
# resource-protection reasoning as user_lifecycle_routes.py's identical
# import comment: it's metadata, not a caller-authorization decision.
from ...user.user_model import UserRole
from ...user.user_schema import UserRead, UserSelfDeleteRequest, UserSelfUpdateResponse, UserUpdate
from ...user_lifecycle.account_deletion_confirm_handler import account_deletion_confirm_handler
from ...user_lifecycle.account_deletion_confirm_schema import AccountDeleteConfirmSchema
from ...user_lifecycle.account_deletion_service import account_deletion_service
from ...user_lifecycle.user_self_deletion_service import finalize_self_deletion
from ...user_session.session_service import session_service
from ..get_or_404.get_or_404 import get_or_404

logger = get_logger(__name__)

# Self-service endpoints only (acting on current_user, never a
# path-parameterized user_email), so this router is never gated by anything
# beyond users:read_own/update_own. Kept separate from
# user_management_routes.py so the two permission tiers can't accidentally
# share a route by being defined in the same file.
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


@router.put("/me", response_model=UserSelfUpdateResponse)
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

    # Password changes revoke other sessions since old credentials may be
    # compromised, keeping the current chain (it supplied the password) and
    # reissuing tokens so it survives the account-version bump.
    #
    # sessions_revoked stays None unless a revoke was attempted below: the
    # password write always succeeds regardless, since blocking it on an
    # unrelated Postgres outage would be worse. False (not raising) lets the
    # caller know, rather than sessions silently staying valid.
    sessions_revoked = None
    if "hashed_password" in prepared_data:
        sessions_revoked = True
        current_payload = await jwt_service.decode_payload(access_token) if access_token else None
        chain_id = current_payload.get("chain") if current_payload else None

        try:
            if chain_id:
                await refresh_token_service.revoke_all_tokens_for_user_except_chain(email, chain_id, db)
            else:
                # Authorization should already have read this cookie. If the
                # chain is still unavailable, revoke the whole account instead.
                await refresh_token_service.revoke_all_tokens_for_user(email, db)
        except TokenVersionUnavailableError:
            sessions_revoked = False
            logger.error("Could not confirm other-session revocation on password change for %s", email)

        if chain_id:
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

    response_payload = UserSelfUpdateResponse.model_validate(updated_user)
    response_payload.sessions_revoked = sessions_revoked
    return response_payload


@router.delete("/me")
async def delete_my_account(
    delete_request: UserSelfDeleteRequest,
    request: Request,
    response: Response,
    current_user: dict = Depends(require_authorization(Permission.USERS_UPDATE_OWN.value, _RESOURCE_TYPE)),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Self-service soft delete: is_active=False + deleted_at=now, same
    mechanics as delete_any_user (user_lifecycle_routes.py), just acting on
    current_user's own row. Deliberately does NOT purge: permanent removal
    only happens via the scheduled grace-period job
    (procrastinate_tasks/account_purge_tasks.py) or an admin's separate
    users:purge action, never synchronously here.

    An account with a password re-authenticates and is deleted immediately
    in this same request. An OAuth-only account (hashed_password is None)
    has no password to re-confirm with, so a stolen access-token cookie
    alone can't prove intent here; see account_deletion_service.py for its
    async, email-confirmed equivalent instead.
    """
    email = current_user["email"]
    user = await get_or_404(user_crud.get_by_email(email, db), "User not found", code="USER_NOT_FOUND")

    if user.role == UserRole.system:
        raise AppError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SYSTEM_USER_CANNOT_BE_DELETED",
            detail="System user cannot be deleted"
        )

    if user.hashed_password is not None:
        # Re-authentication: proves whoever is holding this session's
        # cookies is actually the account owner, same rationale (and same
        # reused hashing call) as the current-password gate on a
        # self-service password change above.
        if not delete_request.current_password or not await password_service.verify_password(
            delete_request.current_password, user.hashed_password
        ):
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CURRENT_PASSWORD_INCORRECT",
                detail="Current password is incorrect",
            )

        await finalize_self_deletion(user, db, request=request)

        # The session was just revoked server-side above; without also
        # clearing these cookies the browser keeps holding now-dead ones,
        # same as logout_handler.py's own cookie clearing.
        token_cookie_handler.clear_tokens_from_cookies(response)

        return {"detail": "Your account has been deleted"}

    # OAuth-only: nothing to synchronously re-confirm with, so this doesn't
    # delete yet - it sends a confirmation link and leaves the account (and
    # this session) untouched until POST /users/me/confirm-delete redeems it.
    await account_deletion_service.send_deletion_email(user, db)

    return {
        "detail": "Check your email to confirm deleting your account",
        "confirmation_required": True,
    }


# POST with the token in the body, not a GET query param (same reasoning as
# /auth/verify-account): a token in a URL ends up in browser history, access
# logs, and Referer headers. Unauthenticated by design, same trust model as
# POST /auth/password-reset/confirm: the signed, single-use token is the
# proof of intent, so this link must work from whatever device/browser the
# caller opened their email in, not just the one that requested deletion.
@router.post("/me/confirm-delete")
@rate_limiter_service.rate_limited("account_delete_confirm")
async def confirm_delete_my_account(
    payload: AccountDeleteConfirmSchema, request: Request, db: AsyncSession = Depends(database.get_session)
):
    return await account_deletion_confirm_handler.handle_confirm_delete(payload.token, db=db, request=request)
