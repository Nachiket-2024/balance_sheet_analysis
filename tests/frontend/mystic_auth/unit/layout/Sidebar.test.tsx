import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import { useLanguageStore } from '@/store/languageStore';
import Sidebar from '@/layout/Sidebar';

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
  });
}

function renderSidebar(
  initialEntries: string[] = ['/'],
  extraItems?: ComponentProps<typeof Sidebar>['extraItems']
) {
  return render(
    <ChakraProvider value={defaultSystem}>
      <MemoryRouter initialEntries={initialEntries}>
        <Sidebar isOpen={false} onNavigate={() => {}} extraItems={extraItems} />
      </MemoryRouter>
    </ChakraProvider>
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

  it('hides Users and Policies links for a caller with no admin permissions', () => {
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

  it('highlights Dashboard as active when the current route is /dashboard', () => {
    renderSidebar(['/dashboard']);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveStyle({ fontWeight: '600' });
    expect(screen.getByRole('link', { name: 'Audit Log' })).toHaveStyle({ fontWeight: '500' });
  });

  it('renders no extra links when extraItems is omitted, unchanged from before this prop existed', () => {
    renderSidebar();

    // Scoped to the nav-links list, not the whole sidebar: the brand text
    // above it is also a link (to /dashboard), which would otherwise count
    // itself here and throw every length/order assertion below off by one.
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
    // Dashboard is order:10, Audit Log is order:40 : 25 lands between them,
    // after Users/Policies too (order:20/30) even though this caller can't
    // see those two (no matching permissions), confirming order is applied
    // to the full merged list, not just to the items actually rendered.
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

  it('translates nav links to Marathi in the plain "mr" mode (unlike the mixed modes)', () => {
    useLanguageStore.getState().setMode('mr');

    renderSidebar();

    expect(screen.getByRole('link', { name: 'डॅशबोर्ड' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Dashboard' })).toBeNull();
  });
});
