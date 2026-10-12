import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import AppLayout from '@/layout/app_layout/AppLayout';

const initialAuthState = useAuthStore.getState();

function renderLayout(props: Pick<ComponentProps<typeof AppLayout>, 'extraNavItems' | 'extraNavbarContent' | 'onOpenCommandPalette'> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AppLayout {...props}>
            <div>page content</div>
          </AppLayout>
        </MemoryRouter>
      </QueryClientProvider>
  );
}

describe('AppLayout', () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
  });

  it('renders its children inside the main content area', () => {
    renderLayout();

    expect(screen.getByText('page content')).toBeInTheDocument();
  });

  it('does not show the mobile nav backdrop until the sidebar is toggled open', () => {
    const { container } = renderLayout();

    expect(container.querySelector('[data-testid="mobile-nav-backdrop"]')).toBeNull();
  });

  it('shows the mobile nav backdrop after the hamburger button is clicked', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));

    expect(container.querySelector('[data-testid="mobile-nav-backdrop"]')).toBeTruthy();
  });

  it('closes the mobile nav when Escape is pressed while it is open', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));
    expect(container.querySelector('[data-testid="mobile-nav-backdrop"]')).toBeTruthy();

    await userEvent.keyboard('{Escape}');

    expect(container.querySelector('[data-testid="mobile-nav-backdrop"]')).toBeNull();
  });

  it('closes the mobile nav when the backdrop is clicked', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));
    const backdrop = container.querySelector('[data-testid="mobile-nav-backdrop"]') as HTMLElement;
    expect(backdrop).toBeTruthy();

    await userEvent.click(backdrop);

    expect(container.querySelector('[data-testid="mobile-nav-backdrop"]')).toBeNull();
  });

  it('renders no extra sidebar links when extraNavItems is omitted', () => {
    renderLayout();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('renders app-supplied extraNavItems in the sidebar alongside the built-in links', () => {
    renderLayout({ extraNavItems: [{ label: 'Extra A', to: '/extra-a' }] });

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Extra A' })).toBeInTheDocument();
  });

  it('keeps app navbar actions and the command-palette trigger in the shared shell', async () => {
    const user = userEvent.setup();
    const openPalette = vi.fn();
    renderLayout({
      extraNavbarContent: <button type="button">App notifications</button>,
      onOpenCommandPalette: openPalette,
    });

    expect(screen.getByRole('button', { name: 'App notifications' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Open search/ }));
    expect(openPalette).toHaveBeenCalledOnce();
  });
});
