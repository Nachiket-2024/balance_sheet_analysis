from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogEntryRead(BaseModel):
    """Schema returned by the audit log query API : mirrors
    AuthorizationAuditLog (see models/audit_log_model.py)."""

    id: int
    user_email: str
    action: str
    resource_type: str
    resource_identifier: str | None
    allowed: bool
    candidate_policy_names: list[str]
    granting_policy_names: list[str]
    failed_conditions: dict[str, list[str]] | None
    context: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
