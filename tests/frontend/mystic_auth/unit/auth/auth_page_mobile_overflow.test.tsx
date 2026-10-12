// Regression: these auth pages' Cards used to render with a fixed pixel `w`
// (e.g. w="400px"), which overflowed a 375px viewport. The fix switched to
// a fluid width (Tailwind's w-full + a max-w-* cap) so the card shrinks to
// fit and only caps on wide screens. These tests pin that a fixed-pixel
// width doesn't come back.
import type { ReactElement } from 'react';
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import LoginPage from '@/auth/login/LoginPage';
import SignupPage from '@/auth/signup/SignupPage';
import PasswordResetRequestPage from '@/auth/password_reset_request/PasswordResetRequestPage';
import PasswordResetConfirmPage from '@/auth/password_reset_confirm/PasswordResetConfirmPage';
import VerifyAccountPage from '@/auth/verify_account/VerifyAccountPage';

function renderPage(ui: ReactElement, initialEntries: string[] = ['/']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

// Card.tsx's base className always includes "rounded-card" (theme/tailwind.css's
// --radius-card token), a stable marker for the card root regardless of what
// width/padding utilities a caller layers on via its own className prop.
// jsdom can't parse Tailwind v4's @theme/@import syntax (hence no
// getComputedStyle-based width check here), so this asserts against the
// className directly: w-full/max-w-* (fluid + capped) is fine, a literal
// pixel width utility (w-[400px]) or inline style width is the regression.
function expectNonFixedPixelWidth(container: HTMLElement) {
  const card = container.querySelector('.rounded-card') as HTMLElement | null;
  expect(card).toBeInstanceOf(HTMLElement);
  expect(card!.className).toMatch(/\bw-full\b/);
  expect(card!.className).not.toMatch(/\bw-\[\d+px\]/);
  expect(card!.style.width).toBe('');
}

describe('auth page Cards no longer use a fixed pixel width (mobile-overflow regression)', () => {
  it('LoginPage', () => {
    const { container } = renderPage(<LoginPage />);
    expectNonFixedPixelWidth(container);
  });

  it('SignupPage', () => {
    const { container } = renderPage(<SignupPage />);
    expectNonFixedPixelWidth(container);
  });

  it('SignupPage stacks Name and Email as separate full-width fields (S1: one shared card width, no side-by-side row)', () => {
    const { container } = renderPage(<SignupPage />);
    const nameInput = container.querySelector('input[placeholder="e.g. Asha Kapoor"]') as HTMLElement;
    const emailInput = container.querySelector('input[placeholder="name@company.com"]') as HTMLElement;
    expect(nameInput).toBeInstanceOf(HTMLElement);
    expect(emailInput).toBeInstanceOf(HTMLElement);
  });

  it('PasswordResetRequestPage', () => {
    const { container } = renderPage(<PasswordResetRequestPage />);
    expectNonFixedPixelWidth(container);
  });

  it('PasswordResetConfirmPage', () => {
    const { container } = renderPage(<PasswordResetConfirmPage />, ['/password-reset-confirm?token=abc']);
    expectNonFixedPixelWidth(container);
  });

  it('VerifyAccountPage', () => {
    const { container } = renderPage(<VerifyAccountPage />, ['/verify-account?token=abc&email=user%40example.com']);
    expectNonFixedPixelWidth(container);
  });
});
