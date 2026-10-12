from fastapi import APIRouter, Depends, Query, Response, status

from ...auth.security.rate_limiting.rate_limit_dashboard_service import rate_limit_dashboard_service
from ...auth.security.rate_limiting.rate_limit_schema import RateLimitEntryRead, RateLimitPageRead, RateLimitSummaryRead
from ...authorization.dependencies.authorization_dependency import require_authorization
from ...authorization.permissions import Permission
from ...core.search_query import SEARCH_QUERY_MAX_LENGTH

router = APIRouter(prefix="/rate-limits", tags=["Rate Limits"])

_READ_DEPENDENCY = Depends(require_authorization(Permission.RATE_LIMITS_READ.value, "rate_limits"))
_RESET_DEPENDENCY = Depends(require_authorization(Permission.RATE_LIMITS_RESET.value, "rate_limits"))


@router.get("/", response_model=RateLimitPageRead)
async def list_rate_limits(
    page: int = Query(default=1, ge=1),
    scope: str | None = Query(
        default=None,
        pattern="^(ip|account|email)$",
        # "email" is login_protection_service's login_lock:email:{email}
        # scope (see rate_limit_dashboard_service.list_active_limits and
        # RateLimitEntry.scope on the frontend). The dashboard's dedicated
        # login-lockout view uses `kind=login_lockouts`; this remains available
        # for direct/API filtering of individual email-scoped counters.
        description="Filter to only ip, account, or email limiters.",
    ),
    endpoint: str | None = Query(default=None, description="Exact match on the rate-limited endpoint name."),
    identifier: str | None = Query(
        default=None,
        max_length=SEARCH_QUERY_MAX_LENGTH,
        description="Substring match on the IP address or account/email identifier.",
    ),
    kind: str | None = Query(default=None, pattern="^(at_limit|login_lockouts)$"),
    sort_by: str = Query(default="endpoint", pattern="^(endpoint|scope|identifier|count|resets_at)$"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: dict = _READ_DEPENDENCY,
):
    # Bounded keyspace walk, capped at RateLimitDashboardService.MAX_SCANNED_KEYS
    # (see list_active_limits' own docstring) - an admin-only, low-QPS page,
    # so this trades a capped read-time walk for real numbered pages instead
    # of a cursor the UI can only step through one page at a time.
    entries, total, truncated = await rate_limit_dashboard_service.list_active_limits(
        page=page,
        page_size=page_size,
        scope=scope,
        endpoint=endpoint,
        identifier=identifier,
        kind=kind,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return RateLimitPageRead(
        entries=[RateLimitEntryRead(**entry) for entry in entries],
        total=total,
        truncated=truncated,
    )


@router.get("/summary", response_model=RateLimitSummaryRead)
async def summarize_rate_limits(current_user: dict = _READ_DEPENDENCY):
    """Return bounded summary counts for the dashboard header."""
    summary = await rate_limit_dashboard_service.summarize_active_limits()
    return RateLimitSummaryRead(**summary)


@router.delete("/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_rate_limit(
    key: str,
    current_user: dict = _RESET_DEPENDENCY,
):
    """Manually clears one counter, e.g. to unblock a legitimate caller
    who tripped a limit. Idempotent (DELETE on an already-absent/expired
    key is a no-op), so this always returns 204 rather than 404."""
    await rate_limit_dashboard_service.reset_counter(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
