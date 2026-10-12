import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import PasswordResetRequestForm from '@/auth/password_reset_request/PasswordResetRequestForm';

const mock = new MockAdapter(api);

function renderForm() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PasswordResetRequestForm />
        </MemoryRouter>
    </QueryClientProvider>
  );
}

async function submit(user: ReturnType<typeof userEvent.setup>, email = 'user@example.com') {
  await user.type(screen.getByLabelText(/email/i), email);
  await user.click(screen.getByRole('button', { name: 'Send reset link' }));
}

describe('PasswordResetRequestForm', () => {
  beforeEach(() => {
    mock.reset();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the success message once the request resolves', async () => {
    mock.onPost('/auth/password-reset/request').reply(200, {
      message: 'If that email exists, a reset link has been sent',
    });

    renderForm();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await submit(user);

    expect(await screen.findByText('If that email exists, a reset link has been sent')).toBeInTheDocument();
  });

  it('shows the error message when the request fails', async () => {
    mock.onPost('/auth/password-reset/request').reply(500, { detail: 'Something went wrong' });

    renderForm();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await submit(user);

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.queryByText('If that email exists, a reset link has been sent')).toBeNull();
  });

  it('starts a cooldown after submit and disables resubmission until it elapses', async () => {
    mock.onPost('/auth/password-reset/request').reply(200, { message: 'sent' });

    renderForm();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await submit(user);
    await screen.findByText('sent');

    expect(mock.history.post).toHaveLength(1);

    // F2: success swaps the form for a result panel; its own resend button
    // shows a "Didn't get it? Resend in Ns" countdown, disabled until it
    // elapses, so clicking it during cooldown must not re-fire.
    const button = screen.getByRole('button', { name: /resend in/i });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(mock.history.post).toHaveLength(1);
  });

  // Regression: the cooldown used to start on click, before the server
  // answered, so a 429 showed "Try again in 60s" on the button at the same
  // time the alert said "Please try again later" - the two contradicted
  // each other. The cooldown must follow the response, not the click.
  it('does not start a cooldown when the request fails', async () => {
    mock.onPost('/auth/password-reset/request').reply(429, { error: 'Please try again later' });

    renderForm();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await submit(user);

    expect(await screen.findByText('Please try again later')).toBeInTheDocument();

    const button = screen.getByRole('button', { name: 'Send reset link' }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);

    await user.click(button);
    expect(mock.history.post).toHaveLength(2);
  });
});
