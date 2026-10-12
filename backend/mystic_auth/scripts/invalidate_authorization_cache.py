import argparse
import asyncio

from ..authorization.caching.authorization_cache_service import authorization_cache_service
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


async def _invalidate(emails: list[str], all_policies: bool) -> None:
    """
    The authorization cache (authorization_cache_service.py,
    _USER_POLICIES_TTL_SECONDS=60) is invalidated automatically by every
    API-driven grant/revoke route, but a write made directly against the
    database - a migration backfill, a one-off support script, a manual
    `psql` fix - bypasses that and leaves affected users seeing a stale
    authorization decision for up to 60 seconds. This script is the
    documented way to close that gap: run it right after any out-of-band
    write that changes who holds what.

    Run after an out-of-band UserPermission write (a direct-permission
    grant/revoke done outside the API), or any direct Policy/UserPolicy
    row edit:
        python -m mystic_auth.scripts.invalidate_authorization_cache --email a@example.com --email b@example.com
    Run after an out-of-band edit to a Policy's own definition (actions/
    resource_type/conditions), which can affect every holder, not just
    one:
        python -m mystic_auth.scripts.invalidate_authorization_cache --all-policies
    The two are independent and can be combined in one invocation.
    """
    unique_emails = set(emails)
    if unique_emails:
        await authorization_cache_service.invalidate_user_policies_bulk(unique_emails)
        await authorization_cache_service.invalidate_user_permissions_bulk(unique_emails)
        print(f"Invalidated cached policies/permissions for {len(unique_emails)} user(s).")
        logger.info("Authorization cache invalidated via CLI for %d user(s)", len(unique_emails))

    if all_policies:
        await authorization_cache_service.invalidate_all_user_policies()
        print("Invalidated the entire cached user_policies namespace.")
        logger.info("Authorization cache (all user_policies) invalidated via CLI")

    if not unique_emails and not all_policies:
        print("Nothing to do: pass --email (one or more) and/or --all-policies. See --help.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Flush the authorization cache after an out-of-band (non-API) database write, "
            "so affected users don't wait out the normal 60-second TTL."
        )
    )
    parser.add_argument(
        "--email",
        action="append",
        default=[],
        help="A user whose cached policies/permissions should be invalidated. Repeatable.",
    )
    parser.add_argument(
        "--all-policies",
        action="store_true",
        help="Flush the entire cached user_policies namespace (use after editing a Policy's own definition).",
    )
    args = parser.parse_args()
    asyncio.run(_invalidate(args.email, args.all_policies))


if __name__ == "__main__":
    main()
