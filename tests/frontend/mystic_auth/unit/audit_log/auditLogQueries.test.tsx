import { describe, expect, it, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import {
    useAuthorizationAuditLogQuery,
    useMyAuthorizationAuditLogQuery,
    useUserAuthorizationAuditLogQuery,
} from "@/audit_log/authorization_log/authorizationLogQueries";
import {
    useSecurityAuditLogQuery,
    useMySecurityAuditLogQuery,
    useLoginTrendQuery,
    useMyLoginTrendQuery,
} from "@/audit_log/security_log/securityLogQueries";

const mock = new MockAdapter(api);

function wrapper({ children }: { children: React.ReactNode }) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => mock.reset());

describe("authorization log queries", () => {
    it("maps paging and filter parameters for the all-users query", async () => {
        mock.onGet("/authorization/audit-log").reply((config) => {
            expect(config.params).toMatchObject({ limit: 25, offset: 25, action: "users:read", resource_type: "users", allowed: true });
            return [200, [{ id: 1 }], { "x-total-count": "26" }];
        });
        const { result } = renderHook(() => useAuthorizationAuditLogQuery(2, 25, {
            action: "users:read", resourceType: "users", allowed: true,
        }), { wrapper });
        await waitFor(() => expect(result.current.data?.total).toBe(26));
        expect(result.current.data?.rows).toEqual([{ id: 1 }]);
    });

    it("queries the caller-scoped authorization endpoint", async () => {
        mock.onGet("/authorization/audit-log/me").reply(200, [], { "x-total-count": "0" });
        const { result } = renderHook(() => useMyAuthorizationAuditLogQuery(1, 50), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
        expect(result.current.data).toEqual({ rows: [], total: 0 });
    });

    it("does not fetch a user-scoped query while disabled or email is empty", async () => {
        mock.onGet(/\/authorization\/audit-log\/users\//).reply(200, []);
        const { result } = renderHook(() => useUserAuthorizationAuditLogQuery("", 1, 50, true), { wrapper });
        await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
        expect(mock.history.get).toHaveLength(0);
    });
});

describe("security log queries", () => {
    it("maps all-users security filters and preserves the total", async () => {
        mock.onGet("/audit/security-log").reply((config) => {
            expect(config.params).toMatchObject({ limit: 10, offset: 10, event_type: "login", ip_address: "203.0.113.1", success: false });
            return [200, [{ id: 4 }], { "x-total-count": "11" }];
        });
        const { result } = renderHook(() => useSecurityAuditLogQuery(2, 10, {
            eventType: "login", ipAddress: "203.0.113.1", success: false,
        }), { wrapper });
        await waitFor(() => expect(result.current.data?.total).toBe(11));
    });

    it("queries the caller-scoped security endpoint", async () => {
        mock.onGet("/audit/security-log/me").reply(200, [], { "x-total-count": "0" });
        const { result } = renderHook(() => useMySecurityAuditLogQuery(1, 50), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    it("fetches the all-users login trend with days and search", async () => {
        mock.onGet("/audit/security-log/login-trend").reply((config) => {
            expect(config.params).toEqual({ days: 30, search: "admin" });
            return [200, [{ date: "2026-01-01", success: 2, failure: 1 }]];
        });
        const { result } = renderHook(() => useLoginTrendQuery(30, "admin"), { wrapper });
        await waitFor(() => expect(result.current.data).toEqual([{ date: "2026-01-01", success: 2, failure: 1 }]));
    });

    it("passes the exact table range to the all-users login trend", async () => {
        mock.onGet("/audit/security-log/login-trend").reply((config) => {
            expect(config.params).toEqual({
                days: 7,
                search: undefined,
                from: "2026-01-01T00:00:00.000Z",
                to: "2026-01-07T23:59:59.999Z",
            });
            return [200, []];
        });
        const { result } = renderHook(() => useLoginTrendQuery(
            7,
            undefined,
            "2026-01-01T00:00:00.000Z",
            "2026-01-07T23:59:59.999Z",
        ), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    it("fetches the caller-scoped login trend without a search parameter", async () => {
        mock.onGet("/audit/security-log/me/login-trend").reply((config) => {
            expect(config.params).toEqual({ days: 7 });
            return [200, []];
        });
        const { result } = renderHook(() => useMyLoginTrendQuery(7), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    it("passes the exact table range to the caller-scoped login trend", async () => {
        mock.onGet("/audit/security-log/me/login-trend").reply((config) => {
            expect(config.params).toEqual({
                days: 1,
                from: "2026-01-07T00:00:00.000Z",
                to: "2026-01-07T23:59:59.999Z",
            });
            return [200, []];
        });
        const { result } = renderHook(() => useMyLoginTrendQuery(
            1,
            "2026-01-07T00:00:00.000Z",
            "2026-01-07T23:59:59.999Z",
        ), { wrapper });
        await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
});
