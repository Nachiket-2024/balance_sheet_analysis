import { Gauge, KeyRound, LockKeyhole, Shield, ShieldCheck, Users, type LucideIcon } from "lucide-react";

// Split out of PolicyCard.tsx: react-refresh/only-export-components forbids
// a component file from also exporting plain constants/functions.

// Mirrors backend/mystic_auth/authorization/dependencies/policy_route_
// dependencies.py's PROTECTED_POLICY_NAMES: the backend already rejects
// deactivating/deleting these, this just disables the controls instead of
// letting the click round-trip to a 403.
export const PROTECTED_POLICY_NAMES = new Set(["self_service", "user_management", "system_superuser"]);

/** Shared resource icons keep policy cards and permission group headers in the
 * same visual language. Unknown resource types use a shield fallback. */
export const RESOURCE_TYPE_ICONS: Record<string, LucideIcon> = {
    users: Users,
    policies: ShieldCheck,
    permissions: KeyRound,
    security_audit: Shield,
    rate_limits: Gauge,
    "*": LockKeyhole,
};

/** Subtle semantic tones help authorized operators scan resource groups without
 * turning each header into a colored badge or decorative tile. */
export function resourceTypeIconTone(resourceType: string): string {
    if (resourceType === "users") return "text-sky-600 dark:text-sky-400";
    if (resourceType === "policies") return "text-violet-600 dark:text-violet-400";
    if (resourceType === "permissions") return "text-amber-600 dark:text-amber-400";
    if (resourceType === "security_audit") return "text-rose-600 dark:text-rose-400";
    if (resourceType === "rate_limits") return "text-cyan-600 dark:text-cyan-400";
    return "text-fg-muted";
}

/** Groups a policy's actions by their verb (the part of "resource:verb"
 * after the colon, up to the first underscore) so the expanded card/dialog
 * reads as "read: 3, update: 2" instead of one long flat wall of badges - a
 * system_superuser-sized policy (18+ actions) used to be 15 rows tall. */
export function groupActionsByVerb(actions: string[]): [string, string[]][] {
    const groups = new Map<string, string[]>();
    for (const action of actions) {
        const afterColon = action.includes(":") ? action.split(":")[1] : action;
        const verb = afterColon.split("_")[0] || afterColon;
        const list = groups.get(verb) ?? [];
        list.push(action);
        groups.set(verb, list);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a.localeCompare(b));
}

/** Turns an internal permission id into the plain-language label shown to
 * authorized operators. Keep the original id available via a tooltip/details view.
 * Unknown/fork action shapes remain readable instead of being discarded. */
export const POLICY_DESCRIPTION_MAX_LENGTH = 160;
export const AUTHORIZATION_DESCRIPTION_MAX_LENGTH = 160;
export const POLICY_NAME_MAX_LENGTH = 100;

/** Defensive read-side guard matching the backend description contract. */
export function displayAuthorizationDescription(description: string | null | undefined, fallback = ""): string {
    const value = description?.trim() || fallback;
    return value.length <= AUTHORIZATION_DESCRIPTION_MAX_LENGTH
        ? value
        : `${value.slice(0, AUTHORIZATION_DESCRIPTION_MAX_LENGTH - 1).trimEnd()}…`;
}

export function formatPolicyActionLabel(action: string): string {
    const [resource, rawVerb] = action.split(":", 2);
    if (!rawVerb) return action.replace(/[_-]+/g, " ");
    const verb = rawVerb.replace(/[_-]+/g, " ").trim();
    const resourceLabel = resource.replace(/[_-]+/g, " ").trim();
    return `${verb.charAt(0).toUpperCase()}${verb.slice(1)} ${resourceLabel}`;
}

/** Turns an internal resource type into the plain-language label shown to
 * authorized operators. The raw value remains the filter/API value. */
export function formatResourceTypeLabel(resourceType: string): string {
    if (resourceType === "*") return "All resource types";
    const words = resourceType.replace(/[_-]+/g, " ").trim();
    return words
        .split(/\s+/)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}
