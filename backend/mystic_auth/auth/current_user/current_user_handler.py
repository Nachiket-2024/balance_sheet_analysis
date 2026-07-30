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
from ...logging.logging_config import get_logger
from ...user_crud.user_crud_collector import user_crud
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class CurrentUserHandler:
    """Resolves the currently authenticated user from an access token."""

    async def get_current_user(self, access_token: str, db) -> dict:
        try:
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No access token provided"
                )

            payload = await jwt_service.verify_token(access_token, expected_type="access")

            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )

            email = payload.get("email")

            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )

            user = await user_crud.get_by_email(email, db)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is deactivated"
                )

            # The real PBAC-derived permission set, not anything computed from role.
            policies = await policy_repository.get_active_policies_for_user(user.email, db)
            permissions = {action for policy in policies for action in (policy.actions or [])}

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
            }

        except SQLAlchemyError as exc:
            logger.error("Database error fetching current user:\n%s", traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            ) from exc

        except HTTPException:
            raise

        except Exception as exc:
            logger.error("Error fetching current user:\n%s", traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            ) from exc


current_user_handler = CurrentUserHandler()
