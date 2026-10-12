import { describe, expect, it } from "vitest";

import { filterDestructivePolicies, groupPoliciesByResourceType, paginatePolicies } from "@/policies/policyListHelpers";
import type { PolicyRead } from "@/api/policies_api";

const policy = (overrides: Partial<PolicyRead>): PolicyRead => ({
    id: 1,
    name: "default_policy",
    description: "Default access",
    actions: ["policies:read"],
    resource_type: "policies",
    conditions: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    created_by: null,
    ...overrides,
});

describe("policy list destructive filtering", () => {
    it("filters the complete set before pagination and keeps name ordering", () => {
        const policies = [
            policy({ id: 1, name: "zeta", actions: ["policies:delete"] }),
            policy({ id: 2, name: "alpha", actions: ["policies:read"] }),
            policy({ id: 3, name: "beta", actions: ["policies:revoke"] }),
        ];

        const filtered = filterDestructivePolicies(policies, {});
        expect(filtered.map(({ name }) => name)).toEqual(["beta", "zeta"]);
        expect(paginatePolicies(filtered, 2, 1).map(({ name }) => name)).toEqual(["zeta"]);
    });

    it("applies the same search, resource, status, and exact-action filters", () => {
        const policies = [
            policy({ name: "active policies", description: "Can remove policies", actions: ["policies:delete"] }),
            policy({ name: "inactive policies", description: "Can remove policies", actions: ["policies:delete"], is_active: false }),
            policy({ name: "user policy", description: "Can remove users", actions: ["users:delete_any"], resource_type: "users" }),
        ];

        expect(filterDestructivePolicies(policies, {
            search: "active",
            resourceType: "policies",
            isActive: true,
            containsAction: "policies:delete",
        }).map(({ name }) => name)).toEqual(["active policies"]);
    });

    it("returns an empty page without changing the complete filtered count", () => {
        const policies = [
            policy({ id: 1, name: "a", actions: ["policies:delete"] }),
            policy({ id: 2, name: "b", actions: ["policies:delete"] }),
        ];
        const filtered = filterDestructivePolicies(policies, {});

        expect(filtered).toHaveLength(2);
        expect(paginatePolicies(filtered, 2, 2)).toHaveLength(0);
    });

    it("groups policies by resource type and sorts each group by name", () => {
        const groups = groupPoliciesByResourceType([
            policy({ name: "zeta", resource_type: "users" }),
            policy({ name: "alpha", resource_type: "policies" }),
            policy({ name: "beta", resource_type: "users" }),
        ]);

        expect(groups.map(([resourceType, policies]) => [resourceType, policies.map(({ name }) => name)])).toEqual([
            ["policies", ["alpha"]],
            ["users", ["beta", "zeta"]],
        ]);
    });
});
