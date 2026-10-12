import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import PermissionsPage from '@/permissions/PermissionsPage';

// Shared fixtures/helpers for PermissionsPage's three test files (list/
// groups, filters, details dialog + errors) - split out of one 408-line
// file to stay under the repo's ~350-line target, see AGENTS.md.

export const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

export function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test Admin',
    email: 'admin@example.com',
    role: 'admin',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

export function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PermissionsPage />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

export const CATALOG = [
  { action: 'users:read_own', resource_type: 'users', description: "Read one's own user profile." },
  { action: 'users:delete_any', resource_type: 'users', description: 'Permanently remove any account.' },
  { action: 'security_audit:read', resource_type: 'security_audit', description: 'Read the security audit trail.' },
];

export const USAGE = [
  {
    action: 'users:read_own',
    resource_type: 'users',
    policies: [{ name: 'self_service', user_count: 5 }],
    policy_user_count: 5,
    direct_grant_count: 0,
    total_user_count: 5,
  },
  {
    action: 'users:delete_any',
    resource_type: 'users',
    policies: [],
    policy_user_count: 0,
    direct_grant_count: 1,
    total_user_count: 1,
  },
  {
    action: 'security_audit:read',
    resource_type: 'security_audit',
    policies: [],
    policy_user_count: 0,
    direct_grant_count: 0,
    total_user_count: 0,
  },
];
