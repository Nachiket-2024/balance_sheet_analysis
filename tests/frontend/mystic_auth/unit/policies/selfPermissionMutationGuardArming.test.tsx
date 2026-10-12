// Covers a bug where selfPermissionMutationGuard.ts was fully built and
// consumed by useSessionEventsStream.ts, but markSelfPermissionMutation()
// was never actually called from any of the mutation hooks it exists to
// protect - so the guard was permanently dead in production (see the
// hooks under test below and bulkAssignmentMutations.ts). This asserts the
// producer side directly, independent of which dialogs currently expose a
// self-targeting action in the UI.
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { queryClient } from '@/core/queryClient';
import { useAuthStore } from '@/store/authStore';
import * as selfPermissionMutationGuard from '@/auth/session_lifecycle/selfPermissionMutationGuard';
import {
  useAssignPolicyMutation,
  useRevokePolicyMutation,
  useRevokePolicyActionMutation,
} from '@/policies/queries/policyMutations';
import { useGrantPermissionMutation, useRevokePermissionMutation } from '@/policies/queries/permissionMutations';
import {
  useBulkAssignPoliciesMutation,
  useBulkRemovePoliciesMutation,
  useBulkAssignPermissionsMutation,
  useBulkRemovePermissionsMutation,
  useBulkUpdateRoleMutation,
} from '@/policies/queries/bulkAssignmentMutations';

const mock = new MockAdapter(api);
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

const SELF_EMAIL = 'admin@example.com';
const OTHER_EMAIL = 'other@example.com';

beforeEach(() => {
  mock.reset();
  queryClient.clear();
  useAuthStore.setState({ email: SELF_EMAIL });
});

describe('single-item mutations arm selfPermissionMutationGuard only for the caller\'s own account', () => {
  it('useAssignPolicyMutation arms the guard when the target is the caller', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost(`/authorization/users/${encodeURIComponent(SELF_EMAIL)}/policies`).reply(200, {});
    const { result } = renderHook(() => useAssignPolicyMutation(), { wrapper });

    result.current.mutate({ userEmail: SELF_EMAIL, policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useAssignPolicyMutation does not arm the guard for another user', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost(`/authorization/users/${encodeURIComponent(OTHER_EMAIL)}/policies`).reply(200, {});
    const { result } = renderHook(() => useAssignPolicyMutation(), { wrapper });

    result.current.mutate({ userEmail: OTHER_EMAIL, policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(0);
  });

  it('useRevokePolicyMutation arms the guard when the target is the caller', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onDelete(`/authorization/users/${encodeURIComponent(SELF_EMAIL)}/policies/self_service`).reply(204);
    const { result } = renderHook(() => useRevokePolicyMutation(), { wrapper });

    result.current.mutate({ userEmail: SELF_EMAIL, policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useRevokePolicyActionMutation arms the guard when the target is the caller', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock
      .onPost(`/authorization/users/${encodeURIComponent(SELF_EMAIL)}/policies/self_service/revoke-action`)
      .reply(200, {});
    const { result } = renderHook(() => useRevokePolicyActionMutation(), { wrapper });

    result.current.mutate({ userEmail: SELF_EMAIL, policyName: 'self_service', action: 'users:read_own' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useGrantPermissionMutation arms the guard when the target is the caller', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost(`/authorization/users/${encodeURIComponent(SELF_EMAIL)}/permissions`).reply(200, {});
    const { result } = renderHook(() => useGrantPermissionMutation(), { wrapper });

    result.current.mutate({ userEmail: SELF_EMAIL, action: 'users:read_own', resource_type: 'users' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useRevokePermissionMutation does not arm the guard for another user', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock
      .onDelete(`/authorization/users/${encodeURIComponent(OTHER_EMAIL)}/permissions/users%3Aread_own`)
      .reply(204);
    const { result } = renderHook(() => useRevokePermissionMutation(), { wrapper });

    result.current.mutate({ userEmail: OTHER_EMAIL, action: 'users:read_own', resourceType: 'users' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(0);
  });
});

describe('bulk mutations arm selfPermissionMutationGuard only when the caller is among the affected users', () => {
  function bulkResponse(emails: string[]) {
    return {
      results: emails.map((email) => ({ user_email: email, status: 'success', identifier: 'self_service' })),
    };
  }

  it('useBulkAssignPoliciesMutation arms the guard when the caller is included in the batch', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/policies/assign').reply(200, bulkResponse([SELF_EMAIL, OTHER_EMAIL]));
    const { result } = renderHook(() => useBulkAssignPoliciesMutation(), { wrapper });

    result.current.mutate({ userEmails: [SELF_EMAIL, OTHER_EMAIL], policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useBulkAssignPoliciesMutation does not arm the guard when the caller is not in the batch', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/policies/assign').reply(200, bulkResponse([OTHER_EMAIL]));
    const { result } = renderHook(() => useBulkAssignPoliciesMutation(), { wrapper });

    result.current.mutate({ userEmails: [OTHER_EMAIL], policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(0);
  });

  it('useBulkRemovePoliciesMutation arms the guard when the caller is included in the batch', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/policies/remove').reply(200, bulkResponse([SELF_EMAIL]));
    const { result } = renderHook(() => useBulkRemovePoliciesMutation(), { wrapper });

    result.current.mutate({ userEmails: [SELF_EMAIL], policyName: 'self_service' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useBulkAssignPermissionsMutation arms the guard when the caller is included in the batch', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/permissions/assign').reply(200, bulkResponse([SELF_EMAIL]));
    const { result } = renderHook(() => useBulkAssignPermissionsMutation(), { wrapper });

    result.current.mutate({ userEmails: [SELF_EMAIL], action: 'users:read_own', resourceType: 'users' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useBulkRemovePermissionsMutation arms the guard when the caller is included in the batch', async () => {
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/permissions/remove').reply(200, bulkResponse([SELF_EMAIL]));
    const { result } = renderHook(() => useBulkRemovePermissionsMutation(), { wrapper });

    result.current.mutate({ userEmails: [SELF_EMAIL], action: 'users:read_own', resourceType: 'users' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(1);
  });

  it('useBulkUpdateRoleMutation never arms the guard, even if the caller somehow appears in the response', async () => {
    // The backend always rejects a self-targeted role change (CANNOT_CHANGE_OWN_ROLE),
    // so the caller's own email should never reach a "success" result here - but this
    // mutation isn't a source of permissions_changed events either way, so it must
    // never arm the guard regardless.
    const markSpy = vi.spyOn(selfPermissionMutationGuard, 'markSelfPermissionMutation');
    mock.onPost('/authorization/bulk/users/role').reply(200, bulkResponse([SELF_EMAIL]));
    const { result } = renderHook(() => useBulkUpdateRoleMutation(), { wrapper });

    result.current.mutate({ userEmails: [SELF_EMAIL], role: 'admin' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(markSpy).toHaveBeenCalledTimes(0);
  });
});
