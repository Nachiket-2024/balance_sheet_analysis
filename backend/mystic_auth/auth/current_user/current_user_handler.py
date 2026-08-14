import traceback

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

# PBAC: resolve the caller's actual *assigned policies* into the set of actions they
# grant, so GET /auth/me exposes real, current permissions, letting clients (the
# frontend, or any future consumer) make authorization-adjacent UI/behavior
# decisions without hardcoding role-name comparisons themselves. Deliberately
# sourced from the user's policies (repository), not their role: two users with
# the identical role can hold different policies and therefore see different
# permissions here.
from ...authorization.repositories.policy_repository import policy_repository
from ...core.errors import AppError
from ...logging.logging_config import get_logger
from ...user_crud.user_crud_collector import user_crud
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

            # The real PBAC-derived permission set, not anything computed from role.
            policies = await policy_repository.get_active_policies_for_user(user.email, db)
            permissions = {action for policy in policies for action in (policy.actions or [])}

            # From the best-effort Postgres mirror (user_sessions), not
            # Redis: real token validity is governed by version counters
            # now (jwt_service.py), which have no "list every live session"
            # operation of their own - a version number says whether ONE
            # presented token is still current, not how many exist.
            #
            # Only computed for GET /auth/me (include_active_sessions=True),
            # not for this same method's other caller, the shared
            # get_current_user dependency behind nearly every protected
            # route: that field is only ever read from the /auth/me
            # response, so every other route was paying for a query whose
            # result it never used. See docs/mystic_auth/authentication/
            # session-management.md#active-session-count-on-authme.
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
