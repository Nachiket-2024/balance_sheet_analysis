import { describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
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

  it('calls onCancel when clicking the backdrop behind the dialog', async () => {
    const { onCancel } = renderDialog();

    // The rest of the page is made inert while the dialog is open, so the
    // backdrop is the only "background" surface a click can actually land
    // on - clicking it is equivalent to clicking anywhere outside the
    // dialog. The outside-click listener attaches on a deferred timer, so
    // give it a tick before clicking.
    await act(() => new Promise((resolve) => setTimeout(resolve, 20)));
    await userEvent.click(document.querySelector('[data-part="backdrop"]') as HTMLElement);
    await act(() => new Promise((resolve) => setTimeout(resolve, 20)));

    expect(onCancel).toHaveBeenCalledOnce();
  });
});
