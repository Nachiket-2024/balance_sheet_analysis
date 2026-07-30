from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.refresh_token_logic.refresh_token_handler import refresh_token_handler
from ...auth.token_logic.token_schema import TokenPairResponseSchema
from ...database.connection import database
from ...logging.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth/refresh", tags=["Refresh Token"])


@router.post("/", response_model=TokenPairResponseSchema)
async def refresh_tokens(request: Request, db: AsyncSession = Depends(database.get_session)):
    """
    Reads the refresh token from the httponly cookie : it's issued httponly
    (token_cookie_handler.py) specifically so client-side JS can never read it,
    meaning it can only reach this endpoint via the cookie the browser attaches
    automatically. Mirrors logout_handler.py's identical extraction pattern.
    """
    refresh_token = request.cookies.get("refresh_token")
    return await refresh_token_handler.handle_refresh_tokens(request, refresh_token, db)
