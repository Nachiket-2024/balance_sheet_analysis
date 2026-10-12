import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import { useLanguageStore } from '@/store/languageStore';
import Sidebar from '@/layout/app_layout/Sidebar';

const initialAuthState = useAuthStore.getState();
const initialLanguageState = useLanguageStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
    brand_color: null,
  });
}

function renderSidebar(
  initialEntries: string[] = ['/'],
  extraItems?: ComponentProps<typeof Sidebar>['extraItems']
) {
  return render(
      <MemoryRouter initialEntries={initialEntries}>
        <Sidebar isOpen={false} onNavigate={() => {}} extraItems={extraItems} />
      </MemoryRouter>
  );
}

describe('Sidebar', () => {
  beforeEach(() => {
    seed([]);
    useLanguageStore.setState(initialLanguageState, true);
    useLanguageStore.getState().setMode('en');
  });

  it('always shows links that require no permission', () => {
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Audit Log' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Account Settings' })).toBeInTheDocument();
  });

  it('hides Users and Policies links for a caller with no matching permissions', () => {
    renderSidebar();

    expect(screen.queryByRole('link', { name: 'Users' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Policies' })).toBeNull();
  });

  it('shows Users and Policies links once the caller holds the matching permissions', () => {
    seed(['users:list_all', 'policies:read']);
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Users' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Policies' })).toBeInTheDocument();
  });

  it('shows the Policies link for a caller holding only policies:create (no policies:read)', () => {
    // Creating a policy needs no visibility into existing ones, unlike
    // update/delete/assign/revoke, which require finding the target
    // through the read-gated list first.
    seed(['policies:create']);
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Policies' })).toBeInTheDocument();
  });

  it('highlights Dashboard as active when the current route is /dashboard', () => {
    renderSidebar(['/dashboard']);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveStyle({ fontWeight: '600' });
    expect(screen.getByRole('link', { name: 'Audit Log' })).toHaveStyle({ fontWeight: '500' });
  });

  it('renders no extra links when extraItems is omitted, unchanged from before this prop existed', () => {
    renderSidebar();

    // Scoped to the nav-links list: the brand text above it is also a
    // link (to /dashboard) and would otherwise be counted too.
    const navLinks = within(screen.getByTestId('nav-links'));
    expect(navLinks.getAllByRole('link')).toHaveLength(3); // Dashboard, Audit Log, Account Settings
  });

  it('renders app-supplied extraItems appended after the built-in links', () => {
    renderSidebar(['/'], [{ label: 'Extra A', to: '/extra-a' }]);

    expect(screen.getByRole('link', { name: 'Extra A' })).toBeInTheDocument();
  });

  it('appends an extraItems link without an order after every built-in one, reproducing the original append-only behavior', () => {
    renderSidebar(['/'], [{ label: 'Extra A', to: '/extra-a' }]);

    const navLinks = within(screen.getByTestId('nav-links'));
    const labels = navLinks.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Audit Log', 'Account Settings', 'Extra A']);
  });

  it('slots an extraItems link between two built-ins using order', () => {
    // Dashboard is order:10, Audit Log is order:40, so 25 lands between
    // them, after Users/Policies (order:20/30) too even though this caller
    // can't see those two: order applies to the full merged list, not just
    // rendered items.
    renderSidebar(['/'], [{ label: 'Extra B', to: '/extra-b', order: 25 }]);

    const navLinks = within(screen.getByTestId('nav-links'));
    const labels = navLinks.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Extra B', 'Audit Log', 'Account Settings']);
  });

  it('sorts multiple extraItems among the built-ins by their own order values', () => {
    renderSidebar(['/'], [
      { label: 'Extra C', to: '/extra-c', order: 45 }, // after Audit Log (40), before Account Settings (50)
      { label: 'Extra B', to: '/extra-b', order: 5 }, // before Dashboard (10)
    ]);

    const navLinks = within(screen.getByTestId('nav-links'));
    const labels = navLinks.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Extra B', 'Dashboard', 'Audit Log', 'Extra C', 'Account Settings']);
  });

  it('keeps multiple order-less extraItems in the order they were given, all after the built-ins', () => {
    renderSidebar(['/'], [
      { label: 'Extra C', to: '/extra-c' },
      { label: 'Extra B', to: '/extra-b' },
    ]);

    const navLinks = within(screen.getByTestId('nav-links'));
    const labels = navLinks.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Audit Log', 'Account Settings', 'Extra C', 'Extra B']);
  });

  it('hides an extraItems link gated by a permission the caller lacks', () => {
    renderSidebar(['/'], [{ label: 'Extra A', to: '/extra-a', permission: 'extra:read' }]);

    expect(screen.queryByRole('link', { name: 'Extra A' })).toBeNull();
  });

  it('shows an extraItems link once the caller holds its required permission', () => {
    seed(['extra:read']);
    renderSidebar(['/'], [{ label: 'Extra A', to: '/extra-a', permission: 'extra:read' }]);

    expect(screen.getByRole('link', { name: 'Extra A' })).toBeInTheDocument();
  });

  it('keeps nav links in English in the mixed English+Hindi mode', () => {
    useLanguageStore.getState().setMode('en+hi');

    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Audit Log' })).toBeInTheDocument();
  });

  it('keeps nav links in English in the mixed English+Marathi mode', () => {
    useLanguageStore.getState().setMode('en+mr');

    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Account Settings' })).toBeInTheDocument();
  });

  it('translates nav links to Marathi in the plain "mr" mode (unlike the mixed modes)', async () => {
    useLanguageStore.getState().setMode('mr');

    renderSidebar();

    // setMode('mr') triggers translations.ts's on-demand language-pack load
    // (translations/translations.ts's loadLanguage - added so non-English
    // packs aren't in the initial bundle, see docs/mystic_auth/concerns/README.md's
    // mobile LCP fix), which resolves after this test's synchronous render.
    // waitFor here, not a synchronous assertion, since the sidebar renders in
    // English until that promise settles.
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'डॅशबोर्ड' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull();
  });
});
