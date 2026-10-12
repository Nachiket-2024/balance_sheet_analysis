import traceback

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

# PBAC: resolves the caller's assigned policies into the actions they grant,
# so GET /auth/me exposes real, current permissions for frontend UI/behavior
# decisions, sourced from policies, not role, since two users with the same
# role can hold different policies.
from ...authorization.repositories.policy_repository import policy_repository

# Direct (bypasses-Policy) grants count too: the real enforcement path
# already merges these with policy-derived actions, so a user granted an
# action directly would otherwise pass every backend check but see none of
# the corresponding UI, since the frontend only reads this permissions list.
from ...authorization.repositories.user_permission_repository import user_permission_repository
from ...core.errors import AppError
from ...logging.logging_config import get_logger
from ...user.user_crud_collector import user_crud
from ...user_session.session_service import session_service
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class CurrentUserHandler:
    """Resolves the currently authenticated user from an access token."""

    async def get_current_user(self, access_token: str, db, include_active_sessions: bool = False) -> dict:
        try:
            if not access_token:
                raise AppError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="NO_ACCESS_TOKEN",
                    detail="No access token provided"
                )

            payload = await jwt_service.verify_token(access_token, expected_type="access")

            if not payload:
                raise AppError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="INVALID_OR_EXPIRED_TOKEN",
                    detail="Invalid or expired token"
                )

            email = payload.get("email")

            if not email:
                raise AppError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="INVALID_TOKEN_PAYLOAD",
                    detail="Invalid token payload"
                )

            user = await user_crud.get_by_email(email, db)

            if not user:
                raise AppError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    code="USER_NOT_FOUND",
                    detail="User not found"
                )

            if not user.is_active:
                raise AppError(
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="ACCOUNT_DEACTIVATED",
                    detail="Account is deactivated"
                )

            # An action only counts if it's usable under the policy that
            # grants it: actions are named "<resource_type>:<verb>", and the
            # real check requires policy.resource_type in (that
            # resource_type, "*"). Without this filter, a mis-scoped action
            # (e.g. "policies:read" on a "users"-scoped policy) would light
            # up UI the backend then 403s on for real requests.
            policies = await policy_repository.get_active_policies_for_user(user.email, db)
            permissions = {
                action
                for policy in policies
                for action in (policy.actions or [])
                if policy.resource_type in (action.split(":", 1)[0], "*")
            }

            # Same resource_type-scoping filter as above, applied to direct
            # grants too: a UserPermission's resource_type is independently
            # editable from its action (see UserPermission's own docstring),
            # so a mis-scoped direct grant must be excluded here exactly
            # like a mis-scoped policy action is, for the identical reason.
            direct_grants = await user_permission_repository.get_active_permissions_for_user(user.email, db)
            permissions |= {
                grant.action
                for grant in direct_grants
                if grant.resource_type in (grant.action.split(":", 1)[0], "*")
            }

            # From the best-effort Postgres mirror (user_sessions), not Valkey:
            # version counters (jwt_service.py) govern real token validity but
            # can't list live sessions. Only computed when include_active_sessions
            # is True (i.e. for GET /auth/me), since every other protected route
            # via get_current_user never reads this field. See
            # docs/mystic_auth/authentication/session-management/list-and-revoke-sessions.md#active-session-count-on-authme.
            active_sessions = (
                await session_service.count_active_sessions(db, user.email) if include_active_sessions else 0
            )

            # permissions is sorted for a stable, deterministic response; set
            # iteration order is not guaranteed. has_password lets the frontend
            # tell an OAuth-only account (hashed_password is None, see
            # oauth2_service.py's login_or_create_user) apart from one with a
            # usable password credential, without exposing the hash itself.
            return {
                "name": user.name,
                "email": user.email,
                "role": user.role.value if user.role else None,
                "permissions": sorted(permissions),
                "has_password": user.hashed_password is not None,
                "created_at": user.created_at.isoformat(),
                "active_sessions": active_sessions,
                # None = using the app default brand scale (app/theme.ts);
                # see user_model.py's brand_color column docstring.
                "brand_color": user.brand_color,
            }

        except SQLAlchemyError as exc:
            logger.error("Database error fetching current user:\n%s", traceback.format_exc())
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="DATABASE_ERROR",
                detail="Database error"
            ) from exc

        except HTTPException:
            raise

        except Exception as exc:
            logger.error("Error fetching current user:\n%s", traceback.format_exc())
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                detail="Internal server error"
            ) from exc


current_user_handler = CurrentUserHandler()
