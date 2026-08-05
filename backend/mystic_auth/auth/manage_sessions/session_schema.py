from datetime import datetime

from pydantic import BaseModel


class SessionRead(BaseModel):
    """
    One row on the Manage Sessions dashboard card. Deliberately never
    exposes current_jti or any other token material - only display metadata
    plus the id used to target a revoke.

    Built manually by session_list_handler.py (not `model_validate` off the
    ORM row directly): `is_current` isn't a column, it's computed by
    comparing each row's jti against the caller's own current session.
    """

    id: int
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime
    is_current: bool
