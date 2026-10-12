# Shared by every repository that turns a free-text `search`/`ip_address`
# query param into a SQL ILIKE match (user_base_crud.py, policy_repository.py,
# both audit log repositories), so the escaping and length cap stay in sync.

# Matches the CSV-export name field's own cap. Generous for a real search
# term, but bounds how much text an ILIKE scan compares per row.
SEARCH_QUERY_MAX_LENGTH = 100

ILIKE_ESCAPE_CHAR = "\\"


def ilike_pattern(value: str) -> str:
    """Builds a `%value%` ILIKE pattern with the caller's own `%`/`_` (and
    the escape char) escaped, so e.g. searching "50%_off" matches that
    literal text instead of being read as LIKE wildcards. Unescaped, a
    search of just "%" or "_" turns into an unindexed full-table scan
    matching every row, and repeating those characters can make that scan
    arbitrarily expensive: a cheap DoS lever otherwise open to any caller.
    Pass the result to `.ilike(pattern, escape=ILIKE_ESCAPE_CHAR)`.
    """
    escaped = (
        value.replace(ILIKE_ESCAPE_CHAR, ILIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{ILIKE_ESCAPE_CHAR}%")
        .replace("_", f"{ILIKE_ESCAPE_CHAR}_")
    )
    return f"%{escaped}%"
