import type { PolicyRead } from "../../api/policies_api";

// Mirrors backend's policy_evaluator.py: a resource_type of "*" matches any
// resource type, not the literal string "*" (see policy_model.py).
export const WILDCARD_RESOURCE_TYPE = "*";

/** A single (action, resource_type) pair: the unit a Policy's `actions`
 * (fanned out against its `resource_type`) and a direct UserPermission
 * grant both resolve to during authorization (see backend's
 * AuthorizationService._get_effective_policies). */
export function grantKey(action: string, resourceType: string): string {
    return `${action}::${resourceType}`;
}

/**
 * Every (action, resource_type) a user already effectively holds, from both
 * grant sources: policies assigned to them (fanned out across each policy's
 * `actions`/`resource_type`) and direct UserPermission grants. Used to
 * decide what's actually new to offer in "assign a policy"/"grant a
 * permission" dropdowns, since a flat name/action check would miss a
 * *different* policy or direct grant already covering the same ground.
 */
export function buildEffectiveGrantKeySet(
    assignedPolicies: Pick<PolicyRead, "actions" | "resource_type">[],
    directGrants: { action: string; resource_type: string }[]
): Set<string> {
    const keys = new Set<string>();
    for (const policy of assignedPolicies) {
        for (const action of policy.actions) {
            keys.add(grantKey(action, policy.resource_type));
        }
    }
    for (const grant of directGrants) {
        keys.add(grantKey(grant.action, grant.resource_type));
    }
    return keys;
}

/** True if the user already effectively holds `action` on `resourceType`,
 * per `effectiveGrantKeys` (see buildEffectiveGrantKeySet). Checks both the
 * exact pair and whether the user holds that action with a wildcard
 * resource_type ("*") - e.g. "system_superuser" granting "policies:read" on
 * "*" already covers "policies:read" on "policies" even though the two
 * pairs are different strings. Not symmetric: holding the action on one
 * specific resource_type does NOT cover a candidate asking for "*" itself,
 * since that grant doesn't reach every other resource type the wildcard
 * would. */
function hasEffectiveGrant(effectiveGrantKeys: Set<string>, action: string, resourceType: string): boolean {
    return (
        effectiveGrantKeys.has(grantKey(action, resourceType)) ||
        effectiveGrantKeys.has(grantKey(action, WILDCARD_RESOURCE_TYPE))
    );
}

/** True if every one of `candidate`'s (action, resource_type) pairs is
 * already in `effectiveGrantKeys`, meaning assigning it would add nothing
 * the user doesn't already have (an exact repeat, a subset of an
 * already-assigned policy, or fully covered by direct grants). A policy
 * granting even one action outside that set still adds value and stays
 * offered. */
export function policyAddsNothingNew(
    candidate: Pick<PolicyRead, "actions" | "resource_type">,
    effectiveGrantKeys: Set<string>
): boolean {
    return candidate.actions.every((action) => hasEffectiveGrant(effectiveGrantKeys, action, candidate.resource_type));
}

/** Drops any (action, resource_type) pair in `grants` whose action already
 * has a wildcard ("*") entry in `wildcardSource` (defaults to `grants`
 * itself). A specific "policies:read" badge next to a "policies:read" on
 * "*" badge is pure duplication, since the wildcard already covers it (same
 * subsumption rule as hasEffectiveGrant, applied to display). The wildcard
 * entry itself is always kept.
 *
 * `wildcardSource` matters because the wildcard covering a direct grant
 * often comes from an assigned POLICY, not another direct grant, e.g. a
 * "system_superuser" policy with resource_type "*" covers a direct
 * "permissions:grant" on "permissions" even though neither directly grants
 * the other. Callers filtering a raw direct-grant list should pass the full
 * effective list (buildEffectiveGrantsWithSource) as `wildcardSource` so a
 * policy-sourced wildcard is honored too.
 *
 * Used by the "Direct permissions"/"Effective permissions" badge lists
 * (AccountStatusCard, UserDetailsDialog). UserPermissionsDialog's revoke
 * list intentionally skips this, since each row there is individually
 * revocable. */
export function dedupeAgainstWildcards<T extends { action: string; resource_type: string }>(
    grants: T[],
    wildcardSource: { action: string; resource_type: string }[] = grants
): T[] {
    const wildcardActions = new Set(
        wildcardSource.filter((g) => g.resource_type === WILDCARD_RESOURCE_TYPE).map((g) => g.action)
    );
    return grants.filter(
        (g) => g.resource_type === WILDCARD_RESOURCE_TYPE || !wildcardActions.has(g.action)
    );
}

/** Same subsumption check as dedupeAgainstWildcards, for a single pair
 * rather than a whole list. The wildcard entry itself is never "subsumed",
 * only a more specific grant can be. */
export function isSubsumedByWildcard(
    target: { action: string; resource_type: string },
    source: { action: string; resource_type: string }[]
): boolean {
    if (target.resource_type === WILDCARD_RESOURCE_TYPE) return false;
    return source.some(
        (g) => g.action === target.action && g.resource_type === WILDCARD_RESOURCE_TYPE
    );
}

/** One (action, resource_type) pair a user effectively holds, plus which
 * policy name(s) and/or a direct grant contributed it - the same pair can
 * come from more than one policy, or from both a policy and a direct grant
 * at once. Powers UserDetailsDialog's grouped-by-resource-type view: a flat
 * badge list can show WHAT a user holds, but not WHY, which is the question
 * "why does this account have this?" actually needs answered. */
export interface EffectiveGrantWithSource {
    action: string;
    resource_type: string;
    policyNames: string[];
    direct: boolean;
}

export function buildEffectiveGrantsWithSource(
    assignedPolicies: Pick<PolicyRead, "name" | "actions" | "resource_type">[],
    directGrants: { action: string; resource_type: string }[]
): EffectiveGrantWithSource[] {
    const byKey = new Map<string, EffectiveGrantWithSource>();
    for (const policy of assignedPolicies) {
        for (const action of policy.actions) {
            const key = grantKey(action, policy.resource_type);
            const existing = byKey.get(key);
            if (existing) existing.policyNames.push(policy.name);
            else byKey.set(key, { action, resource_type: policy.resource_type, policyNames: [policy.name], direct: false });
        }
    }
    for (const grant of directGrants) {
        const key = grantKey(grant.action, grant.resource_type);
        const existing = byKey.get(key);
        if (existing) existing.direct = true;
        else byKey.set(key, { action: grant.action, resource_type: grant.resource_type, policyNames: [], direct: true });
    }
    return [...byKey.values()];
}

/** Groups any resource_type-bearing list into a Map keyed by resource_type,
 * insertion order preserved - the shared grouping step behind every
 * "resource cards" display (UserDetailsDialog, PermissionsPage). */
export function groupByResourceType<T extends { resource_type: string }>(items: T[]): Map<string, T[]> {
    const groups = new Map<string, T[]>();
    for (const item of items) {
        const group = groups.get(item.resource_type);
        if (group) group.push(item);
        else groups.set(item.resource_type, [item]);
    }
    return groups;
}

/** Same "already effectively held" check as policyAddsNothingNew, for a
 * single pair rather than a whole policy's worth. Used by
 * UserPermissionsDialog's direct-grant dropdown, which offers one catalog
 * entry at a time. */
export function isAlreadyEffectivelyGranted(
    effectiveGrantKeys: Set<string>,
    action: string,
    resourceType: string
): boolean {
    return hasEffectiveGrant(effectiveGrantKeys, action, resourceType);
}
