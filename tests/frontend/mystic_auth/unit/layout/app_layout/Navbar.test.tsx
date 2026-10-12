import type { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import { useLanguageStore } from '@/store/languageStore';
import Navbar from '@/layout/app_layout/Navbar';

const initialAuthState = useAuthStore.getState();
const initialLanguageState = useLanguageStore.getState();

function renderNavbar(onToggleSidebar = vi.fn(), extraContent?: ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Navbar onToggleSidebar={onToggleSidebar} extraContent={extraContent} />
        </MemoryRouter>
      </QueryClientProvider>
  );
  return { ...utils, onToggleSidebar };
}

describe('Navbar', () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
    useLanguageStore.setState(initialLanguageState, true);
    useLanguageStore.getState().setMode('en');
  });

  it('shows the signed-in user name when the store has a profile', () => {
    useAuthStore.getState().setProfile({
      name: 'Alice',
      email: 'alice@example.com',
      role: 'user',
      permissions: [],
      has_password: true,
      created_at: '2026-01-15T00:00:00Z',
      active_sessions: 1,
      brand_color: null,
    });

    renderNavbar();

    expect(screen.getByText('Alice')).toBeInTheDocument();
  });

  it('does not render a "Signed in as" line when there is no name in the store', () => {
    renderNavbar();

    expect(screen.queryByText(/Signed in as/)).toBeNull();
  });

  it('calls onToggleSidebar when the mobile menu button is clicked', async () => {
    const { onToggleSidebar } = renderNavbar();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));

    expect(onToggleSidebar).toHaveBeenCalledOnce();
  });

  it('renders app-supplied extraContent in the action cluster', () => {
    renderNavbar(vi.fn(), <button>Notifications</button>);

    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument();
  });

  it('stays in English for the mobile menu toggle even in the mixed English+Hindi mode', () => {
    useLanguageStore.getState().setMode('en+hi');

    renderNavbar();

    expect(screen.getByRole('button', { name: 'Toggle navigation menu' })).toBeInTheDocument();
  });

  it('stays in English for the "Signed in as" line even in the mixed English+Marathi mode', () => {
    useLanguageStore.getState().setMode('en+mr');
    useAuthStore.getState().setProfile({
      name: 'Alice',
      email: 'alice@example.com',
      role: 'user',
      permissions: [],
      has_password: true,
      created_at: '2026-01-15T00:00:00Z',
      active_sessions: 1,
      brand_color: null,
    });

    renderNavbar();

    expect(screen.getByText('Signed in as')).toBeInTheDocument();
  });

  it('translates chrome text to Hindi in the plain "hi" mode (unlike the mixed modes)', async () => {
    useLanguageStore.getState().setMode('hi');

    renderNavbar();

    // setMode('hi') triggers translations.ts's on-demand language-pack load
    // (translations/translations.ts's loadLanguage - added so non-English
    // packs aren't in the initial bundle, see docs/mystic_auth/concerns/README.md's
    // mobile LCP fix), which resolves after this test's synchronous render.
    // waitFor here, not a synchronous assertion, since the navbar renders in
    // English until that promise settles.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'नेविगेशन मेनू टॉगल करें' })).toBeInTheDocument();
    });
  });
});
