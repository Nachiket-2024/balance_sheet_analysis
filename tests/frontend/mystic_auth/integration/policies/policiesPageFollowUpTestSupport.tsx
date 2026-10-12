/* eslint-disable react-refresh/only-export-components -- test support module mixes fixtures/helpers with a small render helper. */
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import PoliciesPage from '@/policies/PoliciesPage';
import { Toaster } from '@/ui/toaster/toaster';

// Shared fixtures/helpers for PoliciesPage's follow-up flow test files
// (guards, dialog/rollback) - split out of one 408-line file to stay under
// the repo's ~350-line target, see AGENTS.md.

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

// withToaster: same opt-in as users_page_bulk_actions.test.tsx - most tests
// here don't care about the toast queue, so only the Undo test mounts it.
function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

export function renderPage({ withToaster = false } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PoliciesPage />
          <LocationProbe />
          {withToaster && <Toaster />}
        </MemoryRouter>
    </QueryClientProvider>
  );
}

// Options for the create/edit form's resource-type-scoped actions
// multi-select (see PolicyFormDialog's selectableActions).
export const PERMISSION_CATALOG = [
  { action: 'users:read_own', resource_type: 'users', description: "Read one's own user profile." },
  { action: 'policies:read', resource_type: 'policies', description: 'Read/list policies.' },
  { action: 'policies:update', resource_type: 'policies', description: "Edit an existing policy's fields." },
];

export const SAMPLE_POLICIES = [
  {
    id: 1,
    name: 'report_viewer',
    description: 'Basic report viewing access',
    actions: ['users:read_own'],
    resource_type: 'users',
    conditions: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    created_by: null,
  },
];
