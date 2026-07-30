import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import { Toaster } from '@/ui/toaster';
import { toaster } from '@/ui/toasterInstance';

describe('Toaster', () => {
  afterEach(async () => {
    // toaster is a module-level singleton (by design : see toasterInstance.ts),
    // so its queue outlives this test's own render tree; clear it and let the
    // removal animation's state update land inside act() before the next test.
    await act(async () => {
      toaster.dismiss();
    });
  });

  it('renders a toast created via the shared toaster singleton, with title and description', async () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <Toaster />
      </ChakraProvider>
    );

    act(() => {
      toaster.create({ title: 'Saved', description: 'Your changes were saved.', type: 'success' });
    });

    await waitFor(() => expect(screen.getByText('Saved')).toBeInTheDocument());
    expect(screen.getByText('Your changes were saved.')).toBeInTheDocument();
  });

  it('renders a loading toast with a spinner instead of the status indicator', async () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <Toaster />
      </ChakraProvider>
    );

    act(() => {
      toaster.create({ title: 'Saving...', type: 'loading' });
    });

    await waitFor(() => expect(screen.getByText('Saving...')).toBeInTheDocument());
  });
});
