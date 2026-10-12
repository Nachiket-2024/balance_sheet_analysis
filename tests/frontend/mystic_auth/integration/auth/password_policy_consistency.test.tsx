// Regression: the forms required a special character but never checked for
// lowercase, while the backend (password_service.validate_password_strength)
// requires upper+lower+digit and has no special-character rule, so
// "PASSWORD1!" passed client validation but was rejected server-side.
// These tests keep the two layers in sync.
import type { ReactElement } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import SignupForm from '@/auth/signup/SignupForm';
import PasswordResetConfirmForm from '@/auth/password_reset_confirm/PasswordResetConfirmForm';

const mock = new MockAdapter(api);

function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('SignupForm password policy matches the backend', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('rejects a password with upper+digit+special but no lowercase, and never calls the API', async () => {
    mock.onPost('/auth/signup').reply(200, { message: 'ok' });
    renderWithProviders(<SignupForm />);

    await userEvent.type(screen.getByPlaceholderText('e.g. Asha Kapoor'), 'Test User');
    await userEvent.type(screen.getByPlaceholderText('name@company.com'), 'test@example.com');
    const passwordInput = screen.getByPlaceholderText('Enter password');
    await userEvent.type(passwordInput, 'PASSWORD1!');
    await userEvent.type(screen.getByPlaceholderText('Confirm password'), 'PASSWORD1!');
    await userEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    // U3: a failing rule is flagged on the field (already shown live in the
    // checklist below it) rather than repeated as prose in an alert.
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
    expect(mock.history.post.filter((r) => r.url === '/auth/signup')).toHaveLength(0);
  }, 15000);

  it('validates required identity fields locally and focuses the first invalid field', async () => {
    mock.onPost('/auth/signup').reply(200, { message: 'ok' });
    renderWithProviders(<SignupForm />);

    await userEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    const nameInput = screen.getByLabelText('Name');
    expect(nameInput).toHaveAttribute('aria-invalid', 'true');
    expect(nameInput).toHaveFocus();
    expect(screen.getByText('Enter your name')).toBeInTheDocument();
    expect(mock.history.post.filter((r) => r.url === '/auth/signup')).toHaveLength(0);
  });

  it('shows a translated email validation message without attaching a generic server error to the email field', async () => {
    mock.onPost('/auth/signup').reply(500, { detail: 'Something went wrong' });
    renderWithProviders(<SignupForm />);

    await userEvent.type(screen.getByLabelText('Name'), 'Test User');
    await userEvent.type(screen.getByLabelText('Email'), 'not-an-email');
    await userEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    expect(screen.getByText('Enter a valid email address')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
    expect(mock.history.post.filter((r) => r.url === '/auth/signup')).toHaveLength(0);

    await userEvent.clear(screen.getByLabelText('Email'));
    await userEvent.type(screen.getByLabelText('Email'), 'test@example.com');
    await userEvent.type(screen.getByPlaceholderText('Enter password'), 'Password1');
    await userEvent.type(screen.getByPlaceholderText('Confirm password'), 'Password1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    expect(await screen.findByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'false');
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
  });

  it('accepts a password with upper+lower+digit even without a special character', async () => {
    mock.onPost('/auth/signup').reply(200, { message: 'ok' });
    renderWithProviders(<SignupForm />);

    await userEvent.type(screen.getByPlaceholderText('e.g. Asha Kapoor'), 'Test User');
    await userEvent.type(screen.getByPlaceholderText('name@company.com'), 'test@example.com');
    await userEvent.type(screen.getByPlaceholderText('Enter password'), 'Password1');
    await userEvent.type(screen.getByPlaceholderText('Confirm password'), 'Password1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    await screen.findByText('Check your email');
    expect(mock.history.post.filter((r) => r.url === '/auth/signup')).toHaveLength(1);
  });
});

describe('PasswordResetConfirmForm password policy matches the backend', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('rejects a password with upper+digit+special but no lowercase, and never calls the API', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(200, { message: 'Password has been reset successfully' });
    renderWithProviders(<PasswordResetConfirmForm token="reset-token-abc" />);

    const passwordInput = screen.getByPlaceholderText('New password');
    await userEvent.type(passwordInput, 'PASSWORD1!');
    await userEvent.type(screen.getByPlaceholderText('Confirm new password'), 'PASSWORD1!');
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    // R1 reuses U3's fix: a failing rule flags the field and moves focus
    // there instead of repeating it as prose in an alert.
    expect(passwordInput).toHaveAttribute('aria-invalid', 'true');
    expect(mock.history.post.filter((r) => r.url === '/auth/password-reset/confirm')).toHaveLength(0);
  });

  it('accepts a password with upper+lower+digit even without a special character', async () => {
    mock.onPost('/auth/password-reset/confirm').reply(200, { message: 'Password has been reset successfully' });
    renderWithProviders(<PasswordResetConfirmForm token="reset-token-abc" />);

    await userEvent.type(screen.getByPlaceholderText('New password'), 'Password1');
    await userEvent.type(screen.getByPlaceholderText('Confirm new password'), 'Password1');
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }));

    await screen.findByText('Password updated');
    expect(mock.history.post.filter((r) => r.url === '/auth/password-reset/confirm')).toHaveLength(1);
  });
});
