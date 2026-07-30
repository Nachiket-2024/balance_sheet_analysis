from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntryRead(BaseModel):
    """Schema returned by the security audit log query API, mirrors
    AuditLog (see audit_log_model.py).

    Field name is event_metadata, matching the ORM model's Python attribute
    (the underlying DB/JSON column is named "metadata", but that name is
    reserved on SQLAlchemy's declarative Base, so the model maps it to a
    differently-named attribute, see audit_log_model.py).
    """

    id: int
    user_email: str | None
    event_type: str
    success: bool
    ip_address: str | None
    user_agent: str | None
    request_id: str | None
    event_metadata: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
