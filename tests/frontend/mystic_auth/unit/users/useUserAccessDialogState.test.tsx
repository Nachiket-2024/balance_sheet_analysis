// Covers useUserAccessDialogState's toggle and immediate result feedback
// behind UserAccessDialog (design/user-access.html): assigning/revoking a
// whole policy, and granting/revoking a direct permission, including
// sensitive actions.
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { queryClient } from '@/core/queryClient';
import { useAuthStore } from '@/store/authStore';
import { useUserAccessDialogState } from '@/users/dialogs/useUserAccessDialogState';

vi.mock('@/ui/toaster/toasterInstance', () => ({
  toaster: { create: vi.fn(), update: vi.fn(), dismiss: vi.fn() },
}));

const mock = new MockAdapter(api);
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

const SELF_EMAIL = 'admin@example.com';
const TARGET_EMAIL = 'amara.chen@example.com';

const encodedTarget = encodeURIComponent(TARGET_EMAIL);

beforeEach(() => {
  mock.reset();
  queryClient.clear();
  useAuthStore.setState({ email: SELF_EMAIL, isAuthenticated: true, permissions: [] });

  mock.onGet(`/authorization/users/${encodedTarget}/policies`).reply(200, { user_email: TARGET_EMAIL, policies: [] });
  mock.onGet(`/authorization/users/${encodedTarget}/permissions`).reply(200, { user_email: TARGET_EMAIL, permissions: [] });
  mock.onGet('/authorization/policies', { params: { limit: 1000, offset: 0 } }).reply(200, [
    { name: 'self_service', description: 'Default for every account', resource_type: 'users', actions: ['read_own'], is_active: true },
  ]);
  mock.onGet('/authorization/permissions/catalog').reply(200, [
    { action: 'users:read_own', resource_type: 'users', description: 'View their own profile' },
    { action: 'users:assign_system_role', resource_type: 'users', description: 'Give someone the system role' },
  ]);
});

function renderState(userEmail = TARGET_EMAIL) {
  return renderHook(() => useUserAccessDialogState(true, userEmail), { wrapper });
}

describe('useUserAccessDialogState: whole-policy assign/revoke', () => {
  it('togglePolicy assigns when not currently assigned', async () => {
    mock.onPost(`/authorization/users/${encodedTarget}/policies`, { policy_name: 'self_service' }).reply(200, {});
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPoliciesQuery.isSuccess).toBe(true));

    act(() => result.current.togglePolicy('self_service'));

    await waitFor(() => expect(result.current.assignMutation.isSuccess).toBe(true));
  });

  it('togglePolicy revokes when currently assigned', async () => {
    mock.onGet(`/authorization/users/${encodedTarget}/policies`).reply(200, {
      user_email: TARGET_EMAIL,
      policies: [{ name: 'self_service', description: '', resource_type: 'users', actions: ['read_own'], is_active: true }],
    });
    mock.onDelete(`/authorization/users/${encodedTarget}/policies/self_service`).reply(204);
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPoliciesQuery.isSuccess).toBe(true));
    expect(result.current.assignedNames.has('self_service')).toBe(true);

    act(() => result.current.togglePolicy('self_service'));

    await waitFor(() => expect(result.current.revokeMutation.isSuccess).toBe(true));
  });
});

describe('useUserAccessDialogState: direct permission grant/revoke', () => {
  it('toggleDirectPermission grants an ordinary action on the first click', async () => {
    mock
      .onPost(`/authorization/users/${encodedTarget}/permissions`, { action: 'users:read_own', resource_type: 'users' })
      .reply(200, {});
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPermissionsQuery.isSuccess).toBe(true));

    act(() => result.current.toggleDirectPermission('users:read_own', 'users'));

    await waitFor(() => expect(result.current.grantMutation.isSuccess).toBe(true));
  });

  it('toggleDirectPermission grants a sensitive action on one click', async () => {
    mock
      .onPost(`/authorization/users/${encodedTarget}/permissions`, { action: 'users:assign_system_role', resource_type: 'users' })
      .reply(200, {});
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPermissionsQuery.isSuccess).toBe(true));

    act(() => result.current.toggleDirectPermission('users:assign_system_role', 'users'));

    await waitFor(() => expect(result.current.grantMutation.isSuccess).toBe(true));
    expect(mock.history.post.length).toBe(1);
  });

  it('toggleDirectPermission revokes an existing direct grant in a single click, even for a destructive action', async () => {
    mock.onGet(`/authorization/users/${encodedTarget}/permissions`).reply(200, {
      user_email: TARGET_EMAIL,
      permissions: [{ id: 1, action: 'users:assign_system_role', resource_type: 'users', conditions: null, is_active: true, assigned_by: 'x' }],
    });
    mock
      .onDelete(`/authorization/users/${encodedTarget}/permissions/${encodeURIComponent('users:assign_system_role')}`, { params: { resource_type: 'users' } })
      .reply(204);
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPermissionsQuery.isSuccess).toBe(true));

    act(() => result.current.toggleDirectPermission('users:assign_system_role', 'users'));

    await waitFor(() => expect(result.current.revokePermissionMutation.isSuccess).toBe(true));
  });
});

describe('useUserAccessDialogState: recentAccessChangesQuery (Details tab "Recent access changes")', () => {
  it('fetches the target user\'s access-change log via the admin route when the caller holds security_audit:read', async () => {
    useAuthStore.setState({ email: SELF_EMAIL, isAuthenticated: true, permissions: ['security_audit:read'] });
    mock
      .onGet(`/audit/security-log/users/${encodedTarget}`)
      .reply(200, [{ id: 1, user_email: TARGET_EMAIL, event_type: 'policy_assigned', success: true, ip_address: null, user_agent: null, request_id: null, event_metadata: { policy_name: 'self_service', assigned_by: SELF_EMAIL }, created_at: '2026-01-01T00:00:00Z' }]);
    const { result } = renderState();

    await waitFor(() => expect(result.current.recentAccessChangesQuery.isSuccess).toBe(true));
    expect(result.current.recentAccessChangesQuery.data).toHaveLength(1);
    expect(result.current.canReadSecurityAudit).toBe(true);
  });

  it('never fires the admin route for another user without security_audit:read - the section is simply omitted', async () => {
    useAuthStore.setState({ email: SELF_EMAIL, isAuthenticated: true, permissions: [] });
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPoliciesQuery.isSuccess).toBe(true));

    expect(result.current.canReadSecurityAudit).toBe(false);
    expect(result.current.recentAccessChangesQuery.fetchStatus).toBe('idle');
    expect(mock.history.get.some((r) => r.url?.includes('/audit/security-log/users/'))).toBe(false);
  });

  it("uses the self-service /me route for the caller's own row, regardless of security_audit:read", async () => {
    useAuthStore.setState({ email: SELF_EMAIL, isAuthenticated: true, permissions: [] });
    mock.onGet('/audit/security-log/me').reply(200, []);
    const { result } = renderHook(() => useUserAccessDialogState(true, SELF_EMAIL), { wrapper });

    await waitFor(() => expect(result.current.recentAccessChangesQuery.isSuccess).toBe(true));
    expect(mock.history.get.some((r) => r.url === '/audit/security-log/me')).toBe(true);
  });
});

describe('useUserAccessDialogState: saveConditions', () => {
  it('rejects invalid JSON without calling the API', async () => {
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPermissionsQuery.isSuccess).toBe(true));

    let error: string | null = null;
    act(() => {
      error = result.current.saveConditions('users:read_own', 'users', '{not valid json');
    });

    expect(error).not.toBeNull();
    expect(mock.history.post.length).toBe(0);
  });

  it('saves valid JSON conditions as a direct grant', async () => {
    mock
      .onPost(`/authorization/users/${encodedTarget}/permissions`, {
        action: 'users:read_own',
        resource_type: 'users',
        conditions: { self_only: true },
      })
      .reply(200, {});
    const { result } = renderState();
    await waitFor(() => expect(result.current.userPermissionsQuery.isSuccess).toBe(true));

    act(() => {
      result.current.saveConditions('users:read_own', 'users', '{"self_only": true}');
    });

    await waitFor(() => expect(result.current.grantMutation.isSuccess).toBe(true));
  });
});
