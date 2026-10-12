import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import PasswordResetConfirmForm from '@/auth/password_reset_confirm/PasswordResetConfirmForm';

// Regression guard: sessions_revoked: false must show a distinct warning,
// not the plain success message, so unrevoked sessions aren't hidden.
const mock = new MockAdapter(api);

function renderForm() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PasswordResetConfirmForm token="valid-token" />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

async function submit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('New password'), 'NewStrongPass456!');
  await user.type(screen.getByLabelText('Confirm new password'), 'NewStrongPass456!');
  await user.click(screen.getByRole('button', { name: 'Reset password' }));
}

describe('PasswordResetConfirmForm', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('shows the plain success message when sessions_revoked is true', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(200, {
      message: 'Password has been reset successfully',
      sessions_revoked: true,
    });

    renderForm();
    await submit(userEvent.setup());

    expect(await screen.findByText("You've been logged out of other devices.")).toBeInTheDocument();
  });

  it('shows a distinct warning when sessions_revoked is false', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(200, {
      message: 'Password has been reset successfully',
      sessions_revoked: false,
    });

    renderForm();
    await submit(userEvent.setup());

    expect(
      await screen.findByText("Your password was reset, but we couldn't sign out your other sessions. Log in and check Manage Sessions.")
    ).toBeInTheDocument();
    expect(screen.queryByText("You've been logged out of other devices.")).toBeNull();
  });

  // Regression: the form used to keep both password fields filled and the
  // button clickable after a successful reset, so submitting again replayed
  // the same request against an already-used token. R2 now replaces the
  // whole form with a result panel, so the old fields/button don't exist at
  // all any more - a stronger guarantee than merely clearing/disabling them.
  it('replaces the form with a result panel after a successful reset', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(200, {
      message: 'Password has been reset successfully',
      sessions_revoked: true,
    });

    renderForm();
    await submit(userEvent.setup());

    expect(await screen.findByText('Password updated')).toBeInTheDocument();
    expect(screen.queryByLabelText('New password')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reset password' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Log in' })).toBeInTheDocument();
    expect(mock.history.post).toHaveLength(1);
  });

  // R3: a dead reset link/code fails the same way on every retry, so the
  // form swaps to a dedicated "request a new link" panel instead of leaving
  // the same doomed form up.
  it('shows the expired-link panel when the token is invalid or expired', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(400, {
      error: 'This password reset link is invalid or has expired',
      code: 'INVALID_OR_EXPIRED_RESET_TOKEN',
    });

    renderForm();
    await submit(userEvent.setup());

    expect(await screen.findByText('This link has expired')).toBeInTheDocument();
    expect(screen.queryByLabelText('New password')).toBeNull();
    expect(screen.getByRole('link', { name: 'Request a new link' })).toBeInTheDocument();
  });

  it('keeps the form available when the backend rejects the password rather than the link', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(400, {
      error: 'This reset link or password is invalid',
      code: 'INVALID_RESET_TOKEN_OR_PASSWORD',
    });

    renderForm();
    await submit(userEvent.setup());

    expect(await screen.findByText('This reset link or password is invalid')).toBeInTheDocument();
    expect(screen.getByLabelText('New password')).toBeInTheDocument();
    expect(screen.queryByText('This link has expired')).toBeNull();
  });
});
