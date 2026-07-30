import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import App from '@app/App';
import { useAuthStore } from '@/store/authStore';

// App.tsx builds its own BrowserRouter internally (rather than accepting one
// from the caller), so the route under test is set via the real browser
// history before each render instead of a MemoryRouter wrapper.
function renderAppAt(path: string) {
  window.history.pushState({}, '', path);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <App />
      </ChakraProvider>
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

    expect(await screen.findByRole('button', { name: 'Login' })).toBeInTheDocument();
  });

  it('redirects an unauthenticated visitor away from a protected route, to /login', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/dashboard');

    await waitFor(() => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });
    expect(await screen.findByRole('button', { name: 'Login' })).toBeInTheDocument();
  });

  it('renders the dashboard for an authenticated visitor', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [],
    });
    renderAppAt('/dashboard');

    expect(await screen.findByText('Welcome to your Dashboard')).toBeInTheDocument();
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

    expect(await screen.findByText('Welcome to your Dashboard')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/dashboard');
  });

  it('redirects an unauthenticated visitor from / to /login', async () => {
    mock.onGet('/auth/me').reply(401);
    renderAppAt('/');

    expect(await screen.findByRole('button', { name: 'Login' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/login');
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
