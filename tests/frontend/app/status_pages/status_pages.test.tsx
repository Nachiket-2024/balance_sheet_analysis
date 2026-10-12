import type { ReactElement } from 'react';
import { describe, it, expect, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import i18next from 'i18next';

import NotFoundPage from '@app/status_pages/NotFoundPage';
import NotAuthorizedPage from '@app/status_pages/NotAuthorizedPage';
import { APP_NAME } from '@/core/settings';

function renderPage(ui: ReactElement) {
  return render(
      <MemoryRouter>{ui}</MemoryRouter>
  );
}

function expectConfiguredBranding() {
  const brand = screen.queryByText(APP_NAME) ?? screen.queryByRole('img', { name: APP_NAME });
  expect(brand).not.toBeNull();
}

// Regression guard for design review bug 7: 403/404 used to render on a bare
// canvas instead of AuthLayout, losing the font size/language/theme toggles
// design.md says stay one click on every page, plus the logo.
describe('NotFoundPage', () => {
  it('renders inside the auth shell with its toggles, logo, and both actions', () => {
    renderPage(<NotFoundPage />);

    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
    expectConfiguredBranding();
    expect(screen.getByRole('button', { name: /switch to (light|dark) mode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go back' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go Home/i })).toBeInTheDocument();
  });

  it('navigates back and home from both actions', () => {
    renderPage(<NotFoundPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }));
    fireEvent.click(screen.getByRole('button', { name: /Go Home/i }));
    expect(screen.getByRole('button', { name: 'Go back' })).toBeInTheDocument();
  });
});

describe('NotAuthorizedPage', () => {
  it('renders inside the auth shell with its toggles, logo, and both actions', () => {
    renderPage(<NotAuthorizedPage />);

    expect(screen.getByText('403')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: "You don't have access to this page" })).toBeInTheDocument();
    // E3: an explicit hint, not just the bare permission message.
    expect(screen.getByText(/ask someone with the required permission/i)).toBeInTheDocument();
    expectConfiguredBranding();
    expect(screen.getByRole('button', { name: /switch to (light|dark) mode/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Go back' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go Home/i })).toBeInTheDocument();
  });

  it('handles both navigation actions', () => {
    renderPage(<NotAuthorizedPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }));
    fireEvent.click(screen.getByRole('button', { name: /Go Home/i }));
    expect(screen.getByText('403')).toBeInTheDocument();
  });
});

describe('status pages in every supported language', () => {
  const languages = ['en', 'hi', 'mr', 'gu'] as const;

  afterEach(() => {
    i18next.changeLanguage('en');
  });

  it.each(languages)('renders %s with no unresolved interpolation placeholders', async (lang) => {
    await i18next.changeLanguage(lang);
    const { container: notFoundContainer } = renderPage(<NotFoundPage />);
    expect(notFoundContainer.textContent?.match(/{{\s*\w+\s*}}/)).toBeNull();

    const { container: notAuthorizedContainer } = renderPage(<NotAuthorizedPage />);
    expect(notAuthorizedContainer.textContent?.match(/{{\s*\w+\s*}}/)).toBeNull();
  });
});
