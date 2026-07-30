import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';

import { useAuthStore } from '@/store/authStore';
import Navbar from '@/layout/Navbar';

const initialAuthState = useAuthStore.getState();

function renderNavbar(onToggleSidebar = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <Navbar onToggleSidebar={onToggleSidebar} />
        </MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>
  );
  return { ...utils, onToggleSidebar };
}

describe('Navbar', () => {
  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true);
  });

  it('shows the signed-in user name when the store has a profile', () => {
    useAuthStore.getState().setProfile({
      name: 'Alice',
      email: 'alice@example.com',
      role: 'user',
      permissions: [],
      has_password: true,
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
});
