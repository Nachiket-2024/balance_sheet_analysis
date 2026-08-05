import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import AppLayout from '@/layout/AppLayout';

const initialAuthState = useAuthStore.getState();

function renderLayout(extraNavItems?: ComponentProps<typeof AppLayout>['extraNavItems']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AppLayout extraNavItems={extraNavItems}>
            <div>page content</div>
          </AppLayout>
        </MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>
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

    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  });

  it('shows the mobile nav backdrop after the hamburger button is clicked', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));

    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();
  });

  it('closes the mobile nav when Escape is pressed while it is open', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));
    expect(container.querySelector('[aria-hidden="true"]')).toBeTruthy();

    await userEvent.keyboard('{Escape}');

    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  });

  it('closes the mobile nav when the backdrop is clicked', async () => {
    const { container } = renderLayout();

    await userEvent.click(screen.getByRole('button', { name: 'Toggle navigation menu' }));
    const backdrop = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(backdrop).toBeTruthy();

    await userEvent.click(backdrop);

    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  });

  it('renders no extra sidebar links when extraNavItems is omitted', () => {
    renderLayout();

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('renders app-supplied extraNavItems in the sidebar alongside the built-in links', () => {
    renderLayout([{ label: 'Extra A', to: '/extra-a' }]);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Extra A' })).toBeInTheDocument();
  });
});
