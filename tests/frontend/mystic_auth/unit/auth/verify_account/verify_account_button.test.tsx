import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import VerifyAccountButton from '@/auth/verify_account/VerifyAccountButton';

const mock = new MockAdapter(api);

function renderButton(token: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <VerifyAccountButton token={token} email="user@example.com" />
    </QueryClientProvider>
  );
}

describe('VerifyAccountButton', () => {
  beforeEach(() => {
    mock.reset();
  });

  // Regression: with no ?token= in the URL, the button stayed enabled and
  // sent an empty token on click (ConfirmDeleteAccountButton already guards
  // this the same way).
  it('is disabled when there is no token', () => {
    renderButton('');

    expect(screen.getByRole('button', { name: 'Verify email' })).toBeDisabled();
  });

  it('is enabled with a token, and disables itself after a failed verification', async () => {
    mock.onPost('/auth/verify-account').reply(400, { error: 'This link is invalid or has expired' });

    renderButton('a-token');
    const button = screen.getByRole('button', { name: 'Verify email' }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);

    await userEvent.click(button);

    expect(await screen.findByText('This link is invalid or has expired')).toBeInTheDocument();
    // Regression: clicking again could only fail the same way, so the button
    // must go disabled instead of staying clickable.
    expect(screen.getByRole('button', { name: 'Verify email' })).toBeDisabled();
    expect(mock.history.post).toHaveLength(1);
  });

  it('disables itself after a successful verification too, so it cannot resubmit', async () => {
    mock.onPost('/auth/verify-account').reply(200, { message: 'Account verified' });

    renderButton('a-token');
    await userEvent.click(screen.getByRole('button', { name: 'Verify email' }));

    expect(await screen.findByText('Account verified')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Verify email' })).toBeDisabled();
  });
});
