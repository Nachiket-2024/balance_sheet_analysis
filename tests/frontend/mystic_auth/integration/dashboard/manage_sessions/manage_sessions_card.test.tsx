import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import ManageSessionsCard from '@/dashboard/manage_sessions/ManageSessionsCard';

const mock = new MockAdapter(api);

const CURRENT_SESSION = {
  id: 1,
  ip_address: '10.0.0.1',
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
  created_at: '2026-01-01T00:00:00Z',
  last_used_at: '2026-01-15T00:00:00Z',
  is_current: true,
};

const OTHER_SESSION = {
  id: 2,
  ip_address: '10.0.0.2',
  user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1',
  created_at: '2026-01-02T00:00:00Z',
  last_used_at: '2026-01-14T00:00:00Z',
  is_current: false,
};

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>
          <ManageSessionsCard />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

describe('ManageSessionsCard', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('shows an error message when GET /auth/sessions fails', async () => {
    mock.onGet('/auth/sessions').reply(500);
    renderCard();

    expect(await screen.findByText('Failed to load your sessions')).toBeInTheDocument();
  });

  it('shows an empty state when there are no active sessions', async () => {
    mock.onGet('/auth/sessions').reply(200, []);
    renderCard();

    expect(await screen.findByText('No active sessions.')).toBeInTheDocument();
  });

  it('lists sessions and flags the current device', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    renderCard();

    expect(await screen.findByText('This device')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Log out' })).toHaveLength(2);
  });

  it('ends another device session via DELETE /auth/sessions/{id}, not /auth/logout', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    mock.onDelete('/auth/sessions/2').reply(200, { message: 'Session revoked' });

    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    const logoutButtons = screen.getAllByRole('button', { name: 'Log out' });
    // OTHER_SESSION renders second (list order from the mock response).
    await user.click(logoutButtons[1]);

    expect(await screen.findByText(/End the session on/)).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Log out' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(mock.history.delete[0].url).toBe('/auth/sessions/2');
    expect(mock.history.post.filter((r) => r.url === '/auth/logout').length).toBe(0);
  });

  it("ends the current device's own row via POST /auth/logout, not DELETE /auth/sessions/{id}", async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION]);
    mock.onPost('/auth/logout').reply(200, { message: 'Logged out successfully' });

    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    await user.click(screen.getByRole('button', { name: 'Log out' }));

    expect(await screen.findByText(/This will log you out of this device now/)).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Log out' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.post.filter((r) => r.url === '/auth/logout').length).toBe(1));
    expect(mock.history.delete.length).toBe(0);
  });
});
