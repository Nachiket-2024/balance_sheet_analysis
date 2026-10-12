import { describe, expect, it } from "vitest";

import { canGrantAction, canGrantPolicy } from "@/authorization/grantability";

describe("grantability", () => {
    it("requires the caller to hold built-in actions", () => {
        expect(canGrantAction("users:delete_any", () => false)).toBe(false);
        expect(canGrantAction("users:delete_any", () => true)).toBe(true);
    });

    it("requires the caller to hold custom business actions too", () => {
        expect(canGrantAction("projects:archive", () => false)).toBe(false);
        expect(canGrantAction("projects:archive", () => true)).toBe(true);
    });

    it("requires every built-in action in a policy to be held", () => {
        const can = (action: string) => action === "users:list_all";
        expect(canGrantPolicy({ actions: ["users:list_all"] }, can)).toBe(true);
        expect(canGrantPolicy({ actions: ["users:list_all", "users:delete_any"] }, can)).toBe(false);
    });
});
