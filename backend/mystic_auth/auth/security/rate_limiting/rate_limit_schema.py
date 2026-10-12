from pydantic import BaseModel


class RateLimitEntryRead(BaseModel):
    """One live Valkey-backed rate-limit counter, as shown on the admin Rate
    Limit Dashboard. `key` is the raw Valkey key (endpoint:scope:identifier),
    kept so the frontend can target DELETE /rate-limits/{key} for a
    row-level Reset without having to reconstruct it client-side."""

    key: str
    endpoint: str
    scope: str
    identifier: str
    count: int
    limit: int
    resets_in_seconds: int | None


class RateLimitPageRead(BaseModel):
    """One numbered page of RateLimitEntryRead. `total` (and any page count
    derived from it) is a floor, not an exact count, when `truncated` is
    true: the keyspace walk stopped at RateLimitDashboardService.MAX_SCANNED_KEYS
    before reaching the end (see list_active_limits' docstring)."""

    entries: list[RateLimitEntryRead]
    total: int
    truncated: bool


class RateLimitSummaryRead(BaseModel):
    """Whole-keyspace summary for the Rate Limit Dashboard header tiles.

    Counts are bounded by the same Valkey scan cap as the list endpoint.  When
    ``truncated`` is true, callers must present them as approximate values.
    """

    total: int
    at_limit: int
    login_lockouts: int
    by_endpoint: dict[str, int]
    by_scope: dict[str, int]
    truncated: bool
