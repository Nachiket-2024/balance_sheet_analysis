import type { PolicyRead } from "../api/policies_api";
import { isDestructiveAction } from "../authorization/destructiveActions";

export interface ClientPolicyFilters {
    search?: string;
    resourceType?: string;
    isActive?: boolean;
    containsAction?: string;
}

/** Applies the page's server-equivalent filters to a complete policy list. */
export function filterDestructivePolicies(
    policies: PolicyRead[],
    filters: ClientPolicyFilters,
): PolicyRead[] {
    const search = filters.search?.trim().toLocaleLowerCase() ?? "";

    return policies
        .filter((policy) => {
            if (search) {
                const haystack = `${policy.name} ${policy.description ?? ""}`.toLocaleLowerCase();
                if (!haystack.includes(search)) return false;
            }
            if (filters.resourceType && policy.resource_type !== filters.resourceType) return false;
            if (filters.isActive !== undefined && policy.is_active !== filters.isActive) return false;
            if (filters.containsAction && !policy.actions.includes(filters.containsAction)) return false;
            return policy.actions.some(isDestructiveAction);
        })
        .sort((a, b) => a.name.localeCompare(b.name));
}

export function paginatePolicies(policies: PolicyRead[], page: number, pageSize: number): PolicyRead[] {
    const start = Math.max(0, page - 1) * pageSize;
    return policies.slice(start, start + pageSize);
}

/** Stable resource-type buckets used anywhere several policies are shown. */
export function groupPoliciesByResourceType(policies: PolicyRead[]): Array<[string, PolicyRead[]]> {
    const groups = new Map<string, PolicyRead[]>();
    for (const policy of policies) {
        const group = groups.get(policy.resource_type);
        if (group) group.push(policy);
        else groups.set(policy.resource_type, [policy]);
    }
    return Array.from(groups.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([resourceType, group]) => [
            resourceType,
            [...group].sort((left, right) => left.name.localeCompare(right.name)),
        ]);
}
