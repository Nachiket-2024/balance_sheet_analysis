import traceback

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from ...audit_log.audit_log_service import SESSION_REVOKED, log_security_event
from ...core.errors import AppError
from ...logging.logging_config import get_logger
from ...user_crud.user_crud_collector import user_crud
from ...user_session.session_repository import session_repository
from ...user_session.session_service import session_service
from ..current_user.current_user_handler import current_user_handler
from ..token_logic.jwt_service import jwt_service

logger = get_logger(__name__)


class SessionRevokeHandler:
    """Ends exactly one of the caller's own sessions, leaving every other
    one untouched."""

    async def revoke_session(
        self,
        access_token: str,
        refresh_token: str | None,
        session_id: int,
        db,
        request: Request | None = None,
    ) -> dict:
        try:
            current_user = await current_user_handler.get_current_user(access_token, db)
            email = current_user["email"]

            user = await user_crud.get_by_email(email, db)
            if not user:
                raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="SESSION_NOT_FOUND", detail="Session not found")

            target = await session_repository.get_by_id(db, session_id)
            if not target or target.user_id != user.id or target.revoked_at is not None:
                raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="SESSION_NOT_FOUND", detail="Session not found")

            current_chain_id = None
            if refresh_token:
                payload = await jwt_service.decode_payload(refresh_token)
                if payload and payload.get("type") == "refresh":
                    current_chain_id = payload.get("chain")

            # Mirrors UserPoliciesDialog's "you cannot revoke your own
            # policies here" guard: ending your own current session through
            # this list would immediately invalidate the very request doing
            # it. Logout (or Logout All) is the dedicated flow for that.
            # Compared by chain_id, not jti - see session_list_handler.py's
            # identical reasoning.
            if current_chain_id and target.chain_id == current_chain_id:
                raise AppError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="CANNOT_REVOKE_CURRENT_SESSION",
                    detail="Use Logout to end your current session",
                )

            revoked = await session_service.revoke_one_session(db, email, session_id)
            if not revoked:
                raise AppError(status_code=status.HTTP_404_NOT_FOUND, code="SESSION_NOT_FOUND", detail="Session not found")

            await log_security_event(
                SESSION_REVOKED,
                db,
                user_email=email,
                success=True,
                request=request,
                metadata={"session_id": session_id},
            )

            return {"message": "Session revoked"}

        except HTTPException:
            raise

        except SQLAlchemyError as exc:
            logger.error("Database error revoking session:\n%s", traceback.format_exc())
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, code="DATABASE_ERROR", detail="Database error"
            ) from exc

        except Exception as exc:
            logger.error("Error revoking session:\n%s", traceback.format_exc())
            raise AppError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                detail="Internal server error",
            ) from exc


session_revoke_handler = SessionRevokeHandler()
