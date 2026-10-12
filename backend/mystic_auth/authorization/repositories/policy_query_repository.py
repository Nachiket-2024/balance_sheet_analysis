from sqlalchemy import any_, asc, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.sql.elements import OrderByList, UnaryExpression

from ...core.search_query import ILIKE_ESCAPE_CHAR, ilike_pattern
from ..models.policy_model import Policy, UserPolicy
from ..schemas.policy_schema import PolicyRead

# Allowlisted sort keys, same rationale as user_base_crud.py's and the audit
# log repositories' identical _SORTABLE_COLUMN(S) constants: never let a
# caller-supplied column name reach the query directly.
_SORTABLE_COLUMN_NAMES = {"name", "resource_type", "is_active", "created_at", "updated_at"}


def _search_filter(search: str | None):
    """Case-insensitive substring match against name or description, same
    shape as UserBaseCRUD's own _search_filter."""
    if not search:
        return None
    pattern = ilike_pattern(search)
    return or_(
        Policy.name.ilike(pattern, escape=ILIKE_ESCAPE_CHAR),
        Policy.description.ilike(pattern, escape=ILIKE_ESCAPE_CHAR),
    )


def _apply_filters(
    stmt,
    search: str | None,
    resource_type: str | None,
    is_active: bool | None,
    contains_action: str | None = None,
    destructive_only: bool = False,
):
    """Shared by get_all (row fetch) and count (X-Total-Count), so a
    filtered page's total always matches what's actually being paged
    through."""
    search_condition = _search_filter(search)
    if search_condition is not None:
        stmt = stmt.where(search_condition)
    if resource_type:
        stmt = stmt.where(Policy.resource_type == resource_type)
    if is_active is not None:
        stmt = stmt.where(Policy.is_active == is_active)
    if contains_action:
        # Policy.actions is a Postgres ARRAY(String); any_() emits
        # `... = ANY(actions)`, an exact-value membership test against the
        # array - "which policies grant invoices:void" not a substring match.
        # (the .any() comparator method used here previously is deprecated
        # for removal as of SQLAlchemy 2.1; any_() is the modern form.)
        stmt = stmt.where(contains_action == any_(Policy.actions))
    if destructive_only:
        # Keep this explicit and catalog-scoped. Custom application actions
        # remain outside MysticAuth's catalog and are not classified here.
        stmt = stmt.where(Policy.actions.overlap([
            "users:deactivate_any",
            "users:delete_any",
            "users:assign_system_role",
            "policies:delete",
            "policies:revoke",
            "permissions:revoke",
            "rate_limits:reset",
        ]))
    return stmt


def _order_by(sort_by: str | None, sort_dir: str) -> list[UnaryExpression | OrderByList]:
    column = getattr(Policy, sort_by, None) if sort_by in _SORTABLE_COLUMN_NAMES else None
    if column is None:
        column = Policy.id
    direction = asc if sort_dir == "asc" else desc
    # id as a secondary key for stable ordering (e.g. many rows sharing the
    # same resource_type), same reasoning as user_base_crud.py's identical
    # tie-breaker.
    return [direction(column), direction(Policy.id)]


class PolicyQueryRepository:
    """
    Read-only policy queries: single/bulk lookup by name, filtered/sorted
    listing, and the matching count for pagination. Split out of
    policy_repository.py, which owns policy mutation (create/update/delete)
    and re-exports every method here as a bound method, so every existing
    `policy_repository.get_all(...)`-style call site keeps working
    unchanged.
    """

    @staticmethod
    async def get_by_name(name: str, db: AsyncSession) -> Policy | None:
        result = await db.execute(select(Policy).where(Policy.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_policies_by_names(names: list[str], db: AsyncSession) -> dict[str, Policy]:
        """Bulk counterpart to get_by_name: resolves every name in `names`
        to its Policy row in one query, keyed by name. Used by
        bulk_policy_routes.py to resolve a batch's target policies without
        one round trip per item."""
        result = await db.execute(select(Policy).where(Policy.name.in_(names)))
        return {policy.name: policy for policy in result.scalars().all()}

    @staticmethod
    async def get_all(
        db: AsyncSession,
        limit: int = 1000,
        offset: int = 0,
        search: str | None = None,
        resource_type: str | None = None,
        is_active: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        contains_action: str | None = None,
        destructive_only: bool = False,
    ) -> list[Policy]:
        # Capped: every other list endpoint in the app (audit log, policy
        # history) bounds its query the same way; this one previously read
        # the whole table unconditionally. `search` is a case-insensitive
        # substring match on name/description; `resource_type`/`is_active`/
        # `contains_action` are exact matches.
        stmt = _apply_filters(select(Policy), search, resource_type, is_active, contains_action, destructive_only)
        stmt = stmt.order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_all_as_read_schemas(
        db: AsyncSession,
        limit: int = 1000,
        offset: int = 0,
        search: str | None = None,
        resource_type: str | None = None,
        is_active: bool | None = None,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        contains_action: str | None = None,
        destructive_only: bool = False,
    ) -> list[PolicyRead]:
        """Same query as get_all, but returns PolicyRead instances built one
        row at a time instead of raw ORM rows.

        Policy/UserPolicy (policy_model.py) is the only pair of mapped
        models in this codebase using SQLAlchemy relationship() (a real
        back-populated cycle at the mapper level, not in the row data
        itself). Validating a whole list of live ORM rows sharing that
        mapper graph in one pydantic-core call intermittently raises
        "Circular reference detected" under from_attributes=True at
        list sizes seen in production, even though every row is
        individually acyclic; validating one row at a time here never
        trips it. No other list route in this codebase touches a model
        with relationship(), so this pattern is scoped to policies only.
        """
        holder_count = func.count(UserPolicy.id).label("holder_count")
        stmt = select(Policy, holder_count).outerjoin(UserPolicy, UserPolicy.policy_id == Policy.id)
        stmt = _apply_filters(stmt, search, resource_type, is_active, contains_action, destructive_only)
        stmt = stmt.group_by(Policy.id).order_by(*_order_by(sort_by, sort_dir)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return [
            PolicyRead.model_validate(row).model_copy(update={"holder_count": int(count)})
            for row, count in result.all()
        ]

    @staticmethod
    async def count(
        db: AsyncSession,
        search: str | None = None,
        resource_type: str | None = None,
        is_active: bool | None = None,
        contains_action: str | None = None,
        destructive_only: bool = False,
    ) -> int:
        """Total matching rows, ignoring limit/offset - lets a caller
        compute how many pages exist (see list_policies' X-Total-Count
        header)."""
        stmt = _apply_filters(
            select(func.count()).select_from(Policy), search, resource_type, is_active, contains_action, destructive_only
        )
        result = await db.execute(stmt)
        return result.scalar_one()


policy_query_repository = PolicyQueryRepository()
