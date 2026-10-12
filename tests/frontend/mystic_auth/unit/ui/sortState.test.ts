import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { nextSortState, useSortState } from "@/ui/hooks/useSortState";
import { sortRateLimitEntries } from "@/rate_limits/sortRateLimitEntries";

const entries = [
    { key: "z", endpoint: "/z", scope: "account" as const, identifier: "b", count: 2, limit: 10, resets_in_seconds: 30 },
    { key: "a", endpoint: "/a", scope: "ip" as const, identifier: "a", count: 9, limit: 10, resets_in_seconds: null },
    { key: "m", endpoint: "/m", scope: "email" as const, identifier: "c", count: 4, limit: 10, resets_in_seconds: 5 },
];

describe("nextSortState", () => {
    it("starts a new key ascending", () => {
        expect(nextSortState({ key: "count", direction: "desc" }, "endpoint")).toEqual({
            key: "endpoint",
            direction: "asc",
        });
    });

    it("toggles the same key from ascending to descending", () => {
        expect(nextSortState({ key: "count", direction: "asc" }, "count")).toEqual({
            key: "count",
            direction: "desc",
        });
    });

    it("toggles the same key from descending to ascending", () => {
        expect(nextSortState({ key: "count", direction: "desc" }, "count")).toEqual({
            key: "count",
            direction: "asc",
        });
    });
});

describe("useSortState", () => {
    it("initializes with the supplied direction and toggles through the hook", () => {
        const { result } = renderHook(() => useSortState("created_at", "asc"));

        expect(result.current.sort).toEqual({ key: "created_at", direction: "asc" });
        act(() => result.current.toggleSort("created_at"));
        expect(result.current.sort).toEqual({ key: "created_at", direction: "desc" });
        act(() => result.current.toggleSort("email"));
        expect(result.current.sort).toEqual({ key: "email", direction: "asc" });
    });
});

describe("sortRateLimitEntries", () => {
    it("sorts strings ascending without mutating the source", () => {
        const source = [...entries];
        expect(sortRateLimitEntries(source, { key: "endpoint", direction: "asc" }).map((e) => e.endpoint)).toEqual([
            "/a",
            "/m",
            "/z",
        ]);
        expect(source).toEqual(entries);
    });

    it("sorts numeric counts descending", () => {
        expect(sortRateLimitEntries(entries, { key: "requests", direction: "desc" }).map((e) => e.count)).toEqual([
            9,
            4,
            2,
        ]);
    });

    it("treats a non-expiring entry as largest for reset sorting", () => {
        expect(sortRateLimitEntries(entries, { key: "resets_at", direction: "asc" }).map((e) => e.identifier)).toEqual([
            "c",
            "b",
            "a",
        ]);
        expect(sortRateLimitEntries(entries, { key: "resets_at", direction: "desc" }).map((e) => e.identifier)).toEqual([
            "a",
            "b",
            "c",
        ]);
    });

    it("returns the same array for an unsupported column", () => {
        expect(sortRateLimitEntries(entries, { key: "unknown", direction: "asc" })).toBe(entries);
    });
});
