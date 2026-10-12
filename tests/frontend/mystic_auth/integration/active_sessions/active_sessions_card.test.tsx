import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import ActiveSessionsCard from '@/active_sessions/ActiveSessionsCard';
import { Toaster } from '@/ui/toaster/toaster';
import { toaster } from '@/ui/toaster/toasterInstance';

const mock = new MockAdapter(api);

const CURRENT_SESSION = {
  id: 1,
  ip_address: '10.0.0.1',
  city: 'Mumbai',
  country: 'India',
  user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
  created_at: '2026-01-01T00:00:00Z',
  last_used_at: '2026-01-15T00:00:00Z',
  is_current: true,
};

const OTHER_SESSION = {
  id: 2,
  ip_address: '10.0.0.2',
  city: null,
  country: null,
  user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1',
  created_at: '2026-01-02T00:00:00Z',
  last_used_at: '2026-01-14T00:00:00Z',
  is_current: false,
};

function renderCard({ withToaster = false } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ActiveSessionsCard />
          {withToaster && <Toaster />}
        </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ActiveSessionsCard', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton that outlives each test's render
    // tree; clear it so a leftover toast from one test can't leak into the next.
    await act(async () => {
      toaster.dismiss();
    });
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

  describe('time columns', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it('shows Signed in and Last seen as a relative time with the exact date and time below', async () => {
      // Only Date is faked, so axios/React Query timers keep running normally.
      vi.useFakeTimers({ toFake: ['Date'] });
      vi.setSystemTime(new Date('2026-01-15T00:02:00Z'));
      mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
      renderCard();

      // Last seen: CURRENT_SESSION 2 minutes before "now", OTHER_SESSION a day before.
      const twoMinutesAgo = await screen.findByText('2 minutes ago');
      expect(screen.getByText('yesterday')).toBeInTheDocument();
      expect(twoMinutesAgo.nextElementSibling?.textContent).toMatch(/^15 Jan 2026, /);

      // Signed in: CURRENT_SESSION 14 days before "now", OTHER_SESSION 13 days.
      const twoWeeksAgo = screen.getByText('2 weeks ago');
      expect(screen.getByText('last week')).toBeInTheDocument();
      expect(twoWeeksAgo.nextElementSibling?.textContent).toMatch(/^01 Jan 2026, /);
    });
  });

  it('shows city and country, the country alone without a city, and a dash when location or IP is unavailable', async () => {
    const COUNTRY_ONLY_NO_IP = { ...OTHER_SESSION, id: 3, country: 'Japan', ip_address: null };
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION, COUNTRY_ONLY_NO_IP]);
    renderCard();

    // City and country render as two stacked lines, not one comma-joined string.
    expect(await screen.findByText('Mumbai')).toBeInTheDocument();
    expect(screen.getByText('India')).toBeInTheDocument();
    // Country without a city shows on its own, not under an "Unknown" city.
    expect(screen.getByText('Japan')).toBeInTheDocument();
    expect(screen.queryByText('Unknown')).toBeNull();
    // No location (OTHER_SESSION) and no IP (session 3): a dash, with the
    // reason still available to screen readers.
    expect(screen.getByText('Location unavailable')).toBeInTheDocument();
    expect(screen.getByText('IP unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('–')).toHaveLength(2);
  });

  it('shows the session count next to the heading without changing the heading name', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    renderCard();

    expect(await screen.findByText('2 active sessions')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Active Sessions' })).toBeInTheDocument();
  });

  it('ends another device session via DELETE /auth/sessions/{id}, not /auth/logout', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    mock.onDelete('/auth/sessions/2').reply(200, { message: 'Session revoked' });

    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    const logoutButtons = screen.getAllByRole('button', { name: 'Log out' });
    // OTHER_SESSION is second in the mock response's list order.
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

  it("never lets the current device's row be selected for bulk log out", async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    expect(rowCheckboxes).toHaveLength(2);

    // Try to select both rows; the current-device row must stay unselected.
    await user.click(rowCheckboxes[0]);
    await user.click(rowCheckboxes[1]);

    expect(await screen.findByText('1 selected')).toBeInTheDocument();
  });

  it('bulk-revokes every selected (non-current) session via one DELETE per id', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    mock.onDelete('/auth/sessions/2').reply(200, { message: 'Session revoked' });

    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    await user.click(rowCheckboxes[1]);

    await user.click(await screen.findByRole('button', { name: 'Log out selected' }));

    expect(await screen.findByText('End 1 sessions')).toBeInTheDocument();
    const confirmButtons = screen.getAllByRole('button', { name: 'Log out selected' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(mock.history.delete[0].url).toBe('/auth/sessions/2');
  });

  it('shows a partial-failure toast when one of the bulk-revoked sessions errors', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION, { ...OTHER_SESSION, id: 3 }]);
    mock.onDelete('/auth/sessions/2').reply(200, { message: 'Session revoked' });
    mock.onDelete('/auth/sessions/3').reply(404, { detail: 'Session not found' });

    renderCard({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText('This device');
    const rowCheckboxes = await screen.findAllByRole('checkbox', { name: 'Select row' });
    await user.click(rowCheckboxes[1]);
    await user.click(rowCheckboxes[2]);

    await user.click(await screen.findByRole('button', { name: 'Log out selected' }));
    const confirmButtons = await screen.findAllByRole('button', { name: 'Log out selected' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(2));
    expect(await screen.findByText('1 sessions ended, 1 failed')).toBeInTheDocument();
  });

  it('logs out everywhere (including this device) via POST /auth/logout/all', async () => {
    mock.onGet('/auth/sessions').reply(200, [CURRENT_SESSION, OTHER_SESSION]);
    mock.onPost('/auth/logout/all').reply(200, { message: 'Logged out of all devices' });

    renderCard();
    const user = userEvent.setup();

    await screen.findByText('This device');
    await user.click(screen.getByRole('button', { name: /Log out everywhere/i }));

    expect(await screen.findByText('Logout all devices')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Logout all' }));

    await waitFor(() => expect(mock.history.post.filter((r) => r.url === '/auth/logout/all').length).toBe(1));
  });
});
