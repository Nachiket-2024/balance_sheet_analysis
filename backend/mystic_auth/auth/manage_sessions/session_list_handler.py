import traceback

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from ...logging.logging_config import get_logger
from ...user_session.session_service import session_service
from ..current_user.current_user_handler import current_user_handler
from ..token_logic.jwt_service import jwt_service
from .session_schema import SessionRead

logger = get_logger(__name__)


class SessionListHandler:
    """Lists the caller's own active Manage Sessions rows."""

    async def list_sessions(
        self, access_token: str, refresh_token: str | None, db
    ) -> list[SessionRead]:
        try:
            current_user = await current_user_handler.get_current_user(access_token, db)
            email = current_user["email"]

            # Best-effort: if the caller's own refresh_token cookie is
            # missing/expired/unparseable, every row just shows as not the
            # current session rather than failing the whole list - the
            # cookie isn't required to know WHICH sessions exist, only to
            # flag one of them as "this device". Compared by chain_id, not
            # jti: jti rotates on every refresh, so a row's current_jti can
            # be momentarily stale mid-rotation, while chain_id stays
            # stable for the session's whole lifetime.
            current_chain_id = None
            if refresh_token:
                payload = await jwt_service.decode_payload(refresh_token)
                if payload and payload.get("type") == "refresh":
                    current_chain_id = payload.get("chain")

            sessions = await session_service.list_sessions(db, email)

            return [
                SessionRead(
                    id=s.id,
                    ip_address=s.ip_address,
                    user_agent=s.user_agent,
                    created_at=s.created_at,
                    last_used_at=s.last_used_at,
                    is_current=bool(s.chain_id) and s.chain_id == current_chain_id,
                )
                for s in sessions
            ]

        except HTTPException:
            raise

        except SQLAlchemyError as exc:
            logger.error("Database error listing sessions:\n%s", traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error"
            ) from exc

        except Exception as exc:
            logger.error("Error listing sessions:\n%s", traceback.format_exc())
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error"
            ) from exc


session_list_handler = SessionListHandler()
