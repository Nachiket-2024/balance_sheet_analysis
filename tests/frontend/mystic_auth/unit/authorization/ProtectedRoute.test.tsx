import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import ProtectedRoute from '@/authorization/ProtectedRoute';

const initialAuthState = useAuthStore.getState();

function seed(options?: { isAuthenticated?: boolean | null; permissions?: string[] }) {
  useAuthStore.setState(initialAuthState, true);
  if (options?.isAuthenticated !== undefined && options.isAuthenticated !== null) {
    useAuthStore.getState().setAuthenticated(options.isAuthenticated);
    if (options.isAuthenticated) {
      useAuthStore.getState().setProfile({
        name: 'Test User',
        email: 'test@example.com',
        role: 'user',
        permissions: options.permissions ?? [],
        has_password: true,
        created_at: '2026-01-15T00:00:00Z',
        active_sessions: 1,
        brand_color: null,
      });
    }
  }
}

function renderProtectedRoute(
  routeProps: { permission?: string | string[]; resourceType?: string } = {},
  initialPath = '/protected'
) {
  return render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute {...routeProps}>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/not-authorized" element={<div>Not Authorized Page</div>} />
          <Route path="/dashboard" element={<div>Dashboard Page</div>} />
        </Routes>
      </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    seed();
  });

  it('shows a loading state while authentication status is unknown', () => {
    seed({ isAuthenticated: null });
    renderProtectedRoute();

    expect(screen.getByText('Verifying session...')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).toBeNull();
    expect(screen.queryByText('Login Page')).toBeNull();
  });

  it('redirects unauthenticated users to /login', () => {
    seed({ isAuthenticated: false });
    renderProtectedRoute();

    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('redirects authenticated users without the required permission to /not-authorized', () => {
    seed({ isAuthenticated: true, permissions: ['users:read_own'] });
    renderProtectedRoute({ permission: 'policies:read' });

    expect(screen.getByText('Not Authorized Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).toBeNull();
    // never /login : the user IS authenticated, just missing a permission
    expect(screen.queryByText('Login Page')).toBeNull();
  });

  it('shows the protected content for authenticated users with the required permission', () => {
    seed({ isAuthenticated: true, permissions: ['policies:read'] });
    renderProtectedRoute({ permission: 'policies:read' });

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('shows the protected content for authenticated users when no permission is required (auth-only)', () => {
    seed({ isAuthenticated: true, permissions: [] });
    renderProtectedRoute();

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('shows the protected content when an array permission is given and the caller holds only one of the listed actions', () => {
    // e.g. /policies, reachable via policies:read OR policies:create (navItems.ts, App.tsx).
    seed({ isAuthenticated: true, permissions: ['policies:create'] });
    renderProtectedRoute({ permission: ['policies:read', 'policies:create'] });

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('redirects to /not-authorized when an array permission is given and the caller holds none of the listed actions', () => {
    seed({ isAuthenticated: true, permissions: ['users:read_own'] });
    renderProtectedRoute({ permission: ['policies:read', 'policies:create'] });

    expect(screen.getByText('Not Authorized Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('shows a loading state (not an immediate /dashboard bounce) the instant permissions are dropped, while the follow-up refetch is still pending', () => {
    // dropPermissions() (authStore.ts) just zeroes the list; a permissions_changed
    // push fires for any account change, not only ones affecting this route. So we
    // must wait for the authoritative GET /auth/me before bouncing off the page.
    seed({ isAuthenticated: true, permissions: ['policies:read'] });
    renderProtectedRoute({ permission: 'policies:read' });
    expect(screen.getByText('Protected Content')).toBeInTheDocument();

    act(() => {
      useAuthStore.getState().dropPermissions();
    });

    expect(screen.getByText('Verifying session...')).toBeInTheDocument();
    expect(screen.queryByText('Dashboard Page')).toBeNull();
    expect(screen.queryByText('Not Authorized Page')).toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('redirects straight to /dashboard (not /not-authorized) once the follow-up refetch confirms the permission is genuinely gone', () => {
    // A route that WAS allowed, unlike the "/not-authorized" case above
    // where it never was: this is useSessionEventsStream's live
    // dropPermissions() pulling access out from under an already-open tab,
    // not a direct navigation to a route the caller never had - but only
    // once setProfile (the resolved GET /auth/me) actually confirms the
    // permission didn't come back, not on the drop alone (see the pending
    // test above).
    seed({ isAuthenticated: true, permissions: ['policies:read'] });
    renderProtectedRoute({ permission: 'policies:read' });

    act(() => {
      useAuthStore.getState().dropPermissions();
    });
    act(() => {
      useAuthStore.getState().setProfile({
        name: 'Test User',
        email: 'test@example.com',
        role: 'user',
        permissions: ['users:read_own'], // policies:read genuinely revoked
        has_password: true,
        created_at: '2026-01-15T00:00:00Z',
        active_sessions: 1,
        brand_color: null,
      });
    });

    expect(screen.getByText('Dashboard Page')).toBeInTheDocument();
    expect(screen.queryByText('Not Authorized Page')).toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('stays on the page (no navigation at all) when the follow-up refetch shows the permission was never actually lost', () => {
    // The exact bug this guards against: an admin changes some OTHER,
    // unrelated permission for this user elsewhere. The SSE push still
    // fires (it carries no detail on what changed), zeroing this tab's
    // permissions and dropping isAllowed to false for an instant - but the
    // resolved profile still holds policies:read, so this route was never
    // actually affected and must never have navigated away.
    seed({ isAuthenticated: true, permissions: ['policies:read'] });
    renderProtectedRoute({ permission: 'policies:read' });

    act(() => {
      useAuthStore.getState().dropPermissions();
    });
    expect(screen.getByText('Verifying session...')).toBeInTheDocument();

    act(() => {
      useAuthStore.getState().setProfile({
        name: 'Test User',
        email: 'test@example.com',
        role: 'user',
        permissions: ['policies:read', 'reports:view'], // unrelated grant; still holds it
        has_password: true,
        created_at: '2026-01-15T00:00:00Z',
        active_sessions: 1,
        brand_color: null,
      });
    });

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
    expect(screen.queryByText('Dashboard Page')).toBeNull();
    expect(screen.queryByText('Not Authorized Page')).toBeNull();
  });
});
