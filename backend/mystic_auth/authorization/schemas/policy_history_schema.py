from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PolicyHistoryEntryRead(BaseModel):
    """Schema returned by the policy history query API : mirrors
    PolicyHistory (see models/policy_history_model.py)."""

    id: int
    policy_id: int | None
    policy_name: str
    change_type: str
    previous_definition: dict | None
    new_definition: dict | None
    changed_fields: list[str] | None
    changed_by: str | None
    change_reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyHistoryCompareResponse(BaseModel):
    """Response for comparing two history entries of the same policy."""

    policy_name: str
    from_history_id: int
    to_history_id: int
    # Full definition snapshot at each entry : a "deleted" entry has no
    # new_definition, so it still needs to resolve to a comparable snapshot
    # (see policy_history_routes.py's _definition_for_entry).
    from_definition: dict | None
    to_definition: dict | None
    changed_fields: list[str]
    diff: dict[str, dict]


class PolicyRollbackRequest(BaseModel):
    """Optional request body for rolling back a policy to a prior version."""

    reason: str | None = Field(default=None, max_length=500)
