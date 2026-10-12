/** Initials from `name` (e.g. "Ada Lovelace" -> "AL"), falling back to the
 * first letter of `email` when `name` is empty. Shared by Navbar's small
 * avatar and DashboardIdentityCard's larger one so both compute the same
 * initials instead of each re-deriving its own. */
export function initialsFor(name: string | null, email: string | null): string {
    const source = name?.trim() ? name.trim() : email?.split("@")[0] ?? "";
    if (!source) return "";
    return source
        .split(/\s+/)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? "")
        .join("");
}
