import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { toaster } from '@/ui/toaster/toasterInstance';

import { mock, seed, renderPage, SAMPLE_POLICIES } from './policiesPageTestSupport';

// PoliciesPage: delete confirmation, and the activate/deactivate switch's
// instant toggle plus Undo. The list and create/edit form live in their
// own sibling file - split out of one 395-line file, see AGENTS.md's
// ~350-line target.

describe('PoliciesPage: status and delete', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    await act(async () => {
      toaster.remove();
    });
  });

  it('deletes a policy after confirming in the ConfirmDialog', async () => {
    seed(['policies:read', 'policies:delete', 'users:read_own']);
    // Delete shows for an already-deactivated non-protected policy.
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], is_active: false }]);
    mock.onGet('/authorization/policies/report_viewer/holders').reply(200, []);
    mock.onDelete('/authorization/policies/report_viewer').reply(204);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(await screen.findByText(/Delete "report_viewer"\?/)).toBeInTheDocument();

    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('deactivates an active policy instantly via the switch, with no confirmation dialog', async () => {
    seed(['policies:read', 'policies:update', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onPut('/authorization/policies/report_viewer').reply(200, { ...SAMPLE_POLICIES[0], is_active: false });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('switch', { name: 'Deactivate' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ is_active: false });
    expect(screen.queryByText(/Deactivate "report_viewer"\?/)).toBeNull();
  });

  it('shows an Undo toast after deactivating, which reactivates on click', async () => {
    seed(['policies:read', 'policies:update', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onPut('/authorization/policies/report_viewer').reply(200, { ...SAMPLE_POLICIES[0], is_active: false });

    // Belt-and-suspenders alongside the file's afterEach: guarantees this
    // specific assertion (which counts "Undo" buttons) never sees a toast
    // left behind by an earlier test in this file that also toggled the
    // switch, however that leftover toast happens to render.
    await act(async () => {
      toaster.remove();
    });

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await user.click(await screen.findByRole('switch', { name: 'Deactivate' }));
    await waitFor(() => expect(mock.history.put.length).toBe(1));

    await user.click(await screen.findByRole('button', { name: 'Undo' }, { timeout: 3000 }));

    await waitFor(() => expect(mock.history.put.length).toBe(2));
    expect(JSON.parse(mock.history.put[1].data)).toEqual({ is_active: true });
  });

  it('reports a failed status Undo instead of leaving the operator without feedback', async () => {
    seed(['policies:read', 'policies:update', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onPut('/authorization/policies/report_viewer').replyOnce(200, { ...SAMPLE_POLICIES[0], is_active: false });
    mock.onPut('/authorization/policies/report_viewer').replyOnce(500);

    renderPage({ withToaster: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('switch', { name: 'Deactivate' }));
    await waitFor(() => expect(mock.history.put.length).toBe(1));
    await user.click(await screen.findByRole('button', { name: 'Undo' }));

    expect(await screen.findByText('Failed to update policy')).toBeInTheDocument();
  });

  it('reactivates an inactive policy directly via the switch, with no confirmation dialog', async () => {
    seed(['policies:read', 'policies:update', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], is_active: false }]);
    mock.onPut('/authorization/policies/report_viewer').reply(200, { ...SAMPLE_POLICIES[0], is_active: true });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('switch', { name: 'Activate' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ is_active: true });
  });
});
