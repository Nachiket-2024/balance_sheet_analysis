import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import App from '@app/App';
import { useAuthStore } from '@/store/authStore';

// App.tsx builds its own BrowserRouter, so we set the route via real
// browser history before each render instead of a MemoryRouter wrapper.
function renderAppAt(path: string) {
  window.history.pushState({}, '', path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <App />
    </QueryClientProvider>
  );
}

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

describe('App routing', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('renders the public login page without requiring a session check to resolve favorably', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/login');

    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument();
  });

  it('redirects an unauthenticated visitor away from a protected route, to /login', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/dashboard');

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument();
  });

  it('renders the dashboard for an authenticated visitor', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [],
    });
    renderAppAt('/dashboard');

    // "Active Sessions" (ActiveSessionsCard's heading) is used as the
    // landmark since Dashboard's identity strip has no unique static
    // heading, and this card renders unconditionally once the user loads
    // (unlike OperationsShortcutsCard, which is permission-gated and renders
    // nothing for this permissions:[] test user). Dashboard is a
    // lazy-loaded route (trackedLazy.ts), so the first render can be slow
    // under coverage instrumentation, hence the longer timeout.
    expect(await screen.findByText('Active Sessions', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
  });

  it('redirects an authenticated visitor from / to /dashboard, updating the URL', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [],
    });
    renderAppAt('/');

    // "Active Sessions" (ActiveSessionsCard's heading) is used as the
    // landmark - see the matching comment above for why.
    expect(await screen.findByText('Active Sessions', {}, { timeout: 5000 })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/dashboard');
  });

  it('shows an unauthenticated visitor the landing page at /, not a redirect', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/');

    // Stays on the landing page (not an auto-redirect to /login): it's a
    // pre-auth marketing page whose own CTAs link to /login and /signup.
    expect(await screen.findByRole('link', { name: 'Get started' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
  });

  it('sends an authenticated visitor without the required permission to /not-authorized', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [], // lacks users:list_all
    });
    renderAppAt('/users');

    expect(await screen.findByText("You don't have permission to view this page")).toBeInTheDocument();
  });

  it('renders a 404 page for an unknown route', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/this-route-does-not-exist');

    expect(await screen.findByText('Oops! Page Not Found')).toBeInTheDocument();
  });
});
