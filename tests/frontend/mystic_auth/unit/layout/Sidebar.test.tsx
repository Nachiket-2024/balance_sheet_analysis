import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import Sidebar from '@/layout/Sidebar';

const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions,
    has_password: true,
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
  });

  it('always shows links that require no permission', () => {
    renderSidebar();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Audit Log' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Profile' })).toBeInTheDocument();
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

    expect(screen.getAllByRole('link')).toHaveLength(3); // Dashboard, Audit Log, Profile
  });

  it('renders app-supplied extraItems appended after the built-in links', () => {
    renderSidebar(['/'], [{ label: 'Projects', to: '/projects' }]);

    expect(screen.getByRole('link', { name: 'Projects' })).toBeInTheDocument();
  });

  it('appends an extraItems link without an order after every built-in one, reproducing the original append-only behavior', () => {
    renderSidebar(['/'], [{ label: 'Projects', to: '/projects' }]);

    const labels = screen.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Audit Log', 'Profile', 'Projects']);
  });

  it('slots an extraItems link between two built-ins using order', () => {
    // Dashboard is order:10, Audit Log is order:40 : 25 lands between them,
    // after Users/Policies too (order:20/30) even though this caller can't
    // see those two (no matching permissions), confirming order is applied
    // to the full merged list, not just to the items actually rendered.
    renderSidebar(['/'], [{ label: 'Companies', to: '/companies', order: 25 }]);

    const labels = screen.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Companies', 'Audit Log', 'Profile']);
  });

  it('sorts multiple extraItems among the built-ins by their own order values', () => {
    renderSidebar(['/'], [
      { label: 'Reports', to: '/reports', order: 45 }, // after Audit Log (40), before Profile (50)
      { label: 'Companies', to: '/companies', order: 5 }, // before Dashboard (10)
    ]);

    const labels = screen.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Companies', 'Dashboard', 'Audit Log', 'Reports', 'Profile']);
  });

  it('keeps multiple order-less extraItems in the order they were given, all after the built-ins', () => {
    renderSidebar(['/'], [
      { label: 'Reports', to: '/reports' },
      { label: 'Companies', to: '/companies' },
    ]);

    const labels = screen.getAllByRole('link').map((el) => el.textContent);
    expect(labels).toEqual(['Dashboard', 'Audit Log', 'Profile', 'Reports', 'Companies']);
  });

  it('hides an extraItems link gated by a permission the caller lacks', () => {
    renderSidebar(['/'], [{ label: 'Projects', to: '/projects', permission: 'projects:read' }]);

    expect(screen.queryByRole('link', { name: 'Projects' })).toBeNull();
  });

  it('shows an extraItems link once the caller holds its required permission', () => {
    seed(['projects:read']);
    renderSidebar(['/'], [{ label: 'Projects', to: '/projects', permission: 'projects:read' }]);

    expect(screen.getByRole('link', { name: 'Projects' })).toBeInTheDocument();
  });
});
