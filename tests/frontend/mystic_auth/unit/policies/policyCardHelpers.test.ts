import { describe, expect, it } from "vitest";

import {
    AUTHORIZATION_DESCRIPTION_MAX_LENGTH,
    PROTECTED_POLICY_NAMES,
    RESOURCE_TYPE_ICONS,
    displayAuthorizationDescription,
    formatPolicyActionLabel,
    formatResourceTypeLabel,
    groupActionsByVerb,
    resourceTypeIconTone,
} from "@/policies/policyCardHelpers";

describe("policy card helpers", () => {
    it("keeps the protected policy list and resource icon fallbacks stable", () => {
        expect(PROTECTED_POLICY_NAMES.has("self_service")).toBe(true);
        expect(PROTECTED_POLICY_NAMES.has("custom_policy")).toBe(false);
        expect(RESOURCE_TYPE_ICONS["*"]).toBeDefined();
        expect(RESOURCE_TYPE_ICONS.users).toBeDefined();
    });

    it.each([
        ["users", "text-sky-600 dark:text-sky-400"],
        ["policies", "text-violet-600 dark:text-violet-400"],
        ["permissions", "text-amber-600 dark:text-amber-400"],
        ["security_audit", "text-rose-600 dark:text-rose-400"],
        ["rate_limits", "text-cyan-600 dark:text-cyan-400"],
        ["unknown", "text-fg-muted"],
    ])("uses the semantic tone for %s resource types", (resourceType, tone) => {
        expect(resourceTypeIconTone(resourceType)).toBe(tone);
    });

    it("groups actions by the first verb component and sorts the groups", () => {
        expect(groupActionsByVerb([
            "users:update_any",
            "policies:read",
            "users:read_own",
            "audit:read",
            "orphan_action",
        ])).toEqual([
            ["orphan", ["orphan_action"]],
            ["read", ["policies:read", "users:read_own", "audit:read"]],
            ["update", ["users:update_any"]],
        ]);
    });

    it("formats known and malformed action identifiers for display", () => {
        expect(formatPolicyActionLabel("users:read_own")).toBe("Read own users");
        expect(formatPolicyActionLabel("security-audit:export_logs")).toBe("Export logs security audit");
        expect(formatPolicyActionLabel("standalone_action-name")).toBe("standalone action name");
    });

    it("formats wildcard, underscored, hyphenated, and blank resource types", () => {
        expect(formatResourceTypeLabel("*")).toBe("All resource types");
        expect(formatResourceTypeLabel("security_audit")).toBe("Security Audit");
        expect(formatResourceTypeLabel("rate-limits")).toBe("Rate Limits");
        expect(formatResourceTypeLabel("  ")).toBe("");
    });

    it("trims descriptions, uses fallbacks, and caps long values", () => {
        expect(displayAuthorizationDescription("  Read access  ")).toBe("Read access");
        expect(displayAuthorizationDescription("   ", "No description")).toBe("No description");

        const longDescription = "x".repeat(AUTHORIZATION_DESCRIPTION_MAX_LENGTH + 20);
        const displayed = displayAuthorizationDescription(longDescription);
        expect(displayed).toHaveLength(AUTHORIZATION_DESCRIPTION_MAX_LENGTH);
        expect(displayed.endsWith("…")).toBe(true);
    });
});
