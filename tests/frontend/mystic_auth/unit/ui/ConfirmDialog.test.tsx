import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import ConfirmDialog from '@/ui/ConfirmDialog';

function renderDialog(props: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const utils = render(
    <ChakraProvider value={defaultSystem}>
      <ConfirmDialog
        isOpen
        title="Delete policy"
        description="This cannot be undone."
        onConfirm={onConfirm}
        onCancel={onCancel}
        {...props}
      />
    </ChakraProvider>
  );
  return { ...utils, onConfirm, onCancel };
}

describe('ConfirmDialog', () => {
  it('renders nothing interactive when closed', () => {
    render(
      <ChakraProvider value={defaultSystem}>
        <ConfirmDialog
          isOpen={false}
          title="Delete policy"
          description="This cannot be undone."
          onConfirm={() => {}}
          onCancel={() => {}}
        />
      </ChakraProvider>
    );

    expect(screen.queryByText('Delete policy')).toBeNull();
  });

  it('renders the title, description, and default confirm label when open', () => {
    renderDialog();

    expect(screen.getByText('Delete policy')).toBeInTheDocument();
    expect(screen.getByText('This cannot be undone.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
  });

  it('renders a custom confirm label when provided', () => {
    renderDialog({ confirmLabel: 'Delete' });

    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  it('calls onConfirm when the confirm button is clicked', async () => {
    const { onConfirm } = renderDialog();

    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it('calls onCancel when the cancel button is clicked', async () => {
    const { onCancel } = renderDialog();

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onCancel).toHaveBeenCalledOnce();
  });

  it('disables the cancel button while isLoading', () => {
    renderDialog({ isLoading: true });

    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
  });
});
