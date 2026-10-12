import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import SignupPage from '@/auth/signup/SignupPage';

// Regression guard: signup previously had no legal-consent links. The
// consent line moved from SignupForm to SignupPage (matching LoginPage's
// shape: OAuth divider, terms line and reciprocal login link all live at
// the page level, not the form), so this now renders the full page.
describe('SignupPage legal consent line', () => {
  it('links to both the Terms of Service and Privacy Policy pages', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <SignupPage />
          </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', '/terms');
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy');
  });

  it('uses account-creation copy for the Google action', () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <SignupPage />
          </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
  });
});
