import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import ConfirmDeleteAccountPage from '@/account_settings/confirm_delete/ConfirmDeleteAccountPage';
import { useAuthStore } from '@/store/authStore';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function renderAtToken(search: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/confirm-delete${search}`]}>
          <Routes>
            <Route path="/confirm-delete" element={<ConfirmDeleteAccountPage />} />
            <Route path="/login" element={<div>Login page</div>} />
          </Routes>
        </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('ConfirmDeleteAccountPage', () => {
  beforeEach(() => {
    mock.reset();
    useAuthStore.setState(initialAuthState, true);
  });

  it('disables the confirm button when the URL has no token', () => {
    renderAtToken('');

    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeDisabled();
  });

  it('confirms deletion and redirects to login on success', async () => {
    mock.onPost('/users/me/confirm-delete', { token: 'delete-token-abc' }).reply(200, {
      message: 'Your account has been deleted',
    });

    renderAtToken('?token=delete-token-abc');
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    await screen.findByText('Login page');
    expect(mock.history.post.length).toBe(1);
  });

  it('shows an error message and leaves the button re-clickable on a non-token failure', async () => {
    mock.onPost('/users/me/confirm-delete').reply(429, { error: 'Too many failed attempts, temporarily locked', code: 'ACCOUNT_LOCKED' });

    renderAtToken('?token=stale-token');
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(await screen.findByText(/temporarily locked/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete my account' })).toBeEnabled();
  });

  it('swaps to an expired-link result panel when the token is dead', async () => {
    mock.onPost('/users/me/confirm-delete').reply(400, { error: 'Invalid or expired token', code: 'INVALID_OR_EXPIRED_DELETE_TOKEN' });

    renderAtToken('?token=stale-token');
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Delete my account' }));

    expect(await screen.findByText('This link has expired')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to log in' })).toHaveAttribute('href', '/login');
    expect(screen.queryByRole('button', { name: 'Delete my account' })).not.toBeInTheDocument();
  });
});
