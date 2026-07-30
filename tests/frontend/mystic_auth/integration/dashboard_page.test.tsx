import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import DashboardPage from '@/dashboard/DashboardPage';

const mock = new MockAdapter(api);

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>
          <DashboardPage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('shows a loading state before the current-user request resolves', () => {
    mock.onGet('/auth/me').reply(() => new Promise(() => {})); // never resolves
    renderDashboard();

    expect(screen.getByText('Loading your details...')).toBeInTheDocument();
  });

  it('renders the current user once GET /auth/me resolves', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [],
    });

    renderDashboard();

    expect(await screen.findByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('user@example.com')).toBeInTheDocument();
    expect(screen.getByText('user')).toBeInTheDocument();
    expect(screen.queryByText('Loading your details...')).toBeNull();
  });

  it('shows an error message when GET /auth/me fails', async () => {
    mock.onGet('/auth/me').reply(500);
    renderDashboard();

    expect(await screen.findByText('Unable to fetch user details')).toBeInTheDocument();
  });

  it('does not render its own logout controls (session controls live in the app shell/Profile now)', async () => {
    mock.onGet('/auth/me').reply(200, {
      name: 'Test User',
      email: 'user@example.com',
      role: 'user',
      permissions: [],
    });

    renderDashboard();

    await screen.findByText('Test User');
    expect(screen.queryByRole('button', { name: 'Logout' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Logout All Devices' })).toBeNull();
  });
});
