import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
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
      });
    }
  }
}

function renderProtectedRoute(
  routeProps: { permission?: string; resourceType?: string } = {},
  initialPath = '/protected'
) {
  return render(
    <ChakraProvider value={defaultSystem}>
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
        </Routes>
      </MemoryRouter>
    </ChakraProvider>
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
});
