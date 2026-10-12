import { describe, it, expect, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor, act } from '@testing-library/react';

import { Toaster } from '@/ui/toaster/toaster';
import { toaster } from '@/ui/toaster/toasterInstance';

describe('Toaster', () => {
  afterEach(async () => {
    // toaster is a module-level singleton (the app-owned toast queue), so
    // its queue outlives this test's render tree; clear it and let the
    // removal animation's state update land inside act() before the next
    // test.
    await act(async () => {
      toaster.dismiss();
    });
  });

  it('renders a toast created via the shared toaster singleton, with title and description', async () => {
    render(<Toaster />);

    act(() => {
      toaster.create({ title: 'Saved', description: 'Your changes were saved.', type: 'success' });
    });

    await waitFor(() => expect(screen.getByText('Saved')).toBeInTheDocument());
    expect(screen.getByText('Your changes were saved.')).toBeInTheDocument();
  });

  it('renders a loading toast with a spinner', async () => {
    render(<Toaster />);

    act(() => {
      toaster.create({ title: 'Saving...', type: 'loading' });
    });

    await waitFor(() => expect(screen.getByText('Saving...')).toBeInTheDocument());
  });

  it('keeps action buttons readable in the toast theme', async () => {
    render(<Toaster />);

    act(() => {
      toaster.create({
        title: 'Permission updated',
        type: 'success',
        action: { label: 'Undo', onClick: () => undefined },
      });
    });

    const undo = await screen.findByRole('button', { name: 'Undo' });
    expect(undo).toHaveClass('!bg-transparent', '!text-inherit');
  });

  it('keeps an action toast accessible and shows a loading state while undo runs', async () => {
    const onUndo = vi.fn();
    render(<Toaster />);

    act(() => {
      toaster.create({
        title: 'Permission updated',
        type: 'success',
        duration: 6000,
        action: { label: 'Undo', onClick: onUndo },
      });
    });

    const notifications = screen.getByLabelText('Notifications');
    expect(notifications).toHaveAttribute('aria-live', 'polite');
    fireEvent.click(await screen.findByRole('button', { name: 'Undo' }));

    expect(onUndo).toHaveBeenCalledOnce();
    expect(notifications.querySelector('.app-toast-loading')).not.toBeNull();
    expect(screen.queryByRole('button', { name: 'Undo' })).toBeNull();
  });
});
