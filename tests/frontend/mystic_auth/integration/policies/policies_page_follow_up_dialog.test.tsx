import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen, act, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { useAuthStore } from '@/store/authStore';
import { toaster } from '@/ui/toaster/toasterInstance';

import { mock, seed, renderPage, SAMPLE_POLICIES } from './policiesPageFollowUpTestSupport';

// PoliciesPage follow-up flows: the details/edit dialog's tabs, keyboard
// navigation, history/rollback, and the delete confirmation's holder count.
// Protected-policy guards and the restricted view live in their own
// sibling file - split out of one 408-line file, see AGENTS.md's
// ~350-line target.

describe('PoliciesPage follow-up flows: dialog', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    await act(async () => {
      toaster.remove();
    });
  });

  it('removes the active edit form when the caller loses policy update authorization', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('tab', { name: 'Edit' }));
    expect(within(dialog).getByDisplayValue('report_viewer')).toBeInTheDocument();

    act(() => {
      useAuthStore.getState().setProfile({
        name: 'Test Admin',
        email: 'admin@example.com',
        role: 'admin',
        permissions: ['policies:read'],
        has_password: true,
        created_at: '2026-01-15T00:00:00Z',
        active_sessions: 1,
        brand_color: null,
      });
    });

    await waitFor(() => {
      expect(within(screen.getByRole('dialog')).queryByDisplayValue('report_viewer')).toBeNull();
      expect(screen.getByText(/authorization to edit this policy changed/i)).toBeInTheDocument();
    });
  });

  it('keeps protected policy editing visible but disabled in the details dialog', async () => {
    seed(['policies:read', 'policies:update']);
    const protectedPolicy = { ...SAMPLE_POLICIES[0], name: 'system_superuser', resource_type: '*', actions: ['policies:read'] };
    mock.onGet('/authorization/policies').reply(200, [protectedPolicy]);
    mock.onGet('/authorization/policies/system_superuser/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('tab', { name: 'Edit' })).toBeDisabled();
    expect(within(dialog).getByRole('tab', { name: 'Details' })).toHaveAttribute('aria-selected', 'true');
  });

  it('prompts to discard unsaved changes when closing a dirty form', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'draft_policy');
    await user.click(screen.getByRole('button', { name: 'Close' }));

    expect(await screen.findByText('Discard unsaved changes?')).toBeInTheDocument();
    const cancelButtons = screen.getAllByRole('button', { name: 'Cancel' });
    await user.click(cancelButtons[cancelButtons.length - 1]);
    expect(screen.getByDisplayValue('draft_policy')).toBeInTheDocument();
  });

  it('navigates authorized operators to Users filtered by the selected policy', async () => {
    seed(['policies:read', 'users:list_all']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(await screen.findByRole('button', { name: 'View policy holders' }));

    expect(screen.getByTestId('location')).toHaveTextContent('/users?policy=report_viewer');
  });

  it('uses the policy details action hierarchy and only exposes Edit to an authorized operator', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    const detailsDialog = await screen.findByRole('dialog');
    expect(within(detailsDialog).getByRole('tab', { name: 'Details' })).toHaveAttribute('aria-selected', 'true');
    expect(within(detailsDialog).getByRole('tab', { name: 'Edit' })).toBeInTheDocument();
    expect(within(detailsDialog).queryByRole('button', { name: 'View policy holders' })).toBeNull();
    const closeButton = within(detailsDialog).getByRole('button', { name: 'Close' });
    expect(closeButton).toBeInTheDocument();
  });

  it('switches between policy details and editing in the same dialog', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('tab', { name: 'Edit' })).toHaveAttribute('aria-selected', 'true');
    expect(within(dialog).getByDisplayValue('report_viewer')).toBeInTheDocument();
    expect(screen.getAllByRole('dialog')).toHaveLength(1);

    await user.click(within(dialog).getByRole('tab', { name: 'Details' }));
    expect(within(screen.getByRole('dialog')).getAllByText('report_viewer').length).toBeGreaterThan(0);
    expect(screen.queryByDisplayValue('report_viewer')).toBeNull();
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
  });

  it('supports keyboard navigation across the policy dialog tabs', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    const detailsTab = within(screen.getByRole('dialog')).getByRole('tab', { name: 'Details' });
    detailsTab.focus();
    await user.keyboard('{ArrowRight}');

    const editTab = within(screen.getByRole('dialog')).getByRole('tab', { name: 'Edit' });
    await waitFor(() => {
      expect(editTab).toHaveAttribute('aria-selected', 'true');
      expect(editTab).toHaveFocus();
    });

    await user.keyboard('{Home}');
    await waitFor(() => {
      const activeDetailsTab = within(screen.getByRole('dialog')).getByRole('tab', { name: 'Details' });
      expect(activeDetailsTab).toHaveAttribute('aria-selected', 'true');
      expect(activeDetailsTab).toHaveFocus();
    });
  });

  it('shows recent policy changes in the details dialog', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, [
      { id: 2, policy_id: 1, policy_name: 'report_viewer', change_type: 'updated', previous_definition: null, new_definition: null, changed_fields: ['description'], changed_by: 'admin@example.com', change_reason: null, created_at: '2026-02-01T00:00:00Z' },
      { id: 1, policy_id: 1, policy_name: 'report_viewer', change_type: 'created', previous_definition: null, new_definition: null, changed_fields: null, changed_by: 'admin@example.com', change_reason: null, created_at: '2026-01-01T00:00:00Z' },
    ]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));

    expect(await screen.findByText('Updated description')).toBeInTheDocument();
    expect(screen.getByText('Created this policy')).toBeInTheDocument();
  });

  it('confirms and submits an authorized policy rollback', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, [
      { id: 2, policy_id: 1, policy_name: 'report_viewer', change_type: 'updated', previous_definition: { name: 'report_viewer', description: 'Old', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true }, new_definition: { name: 'report_viewer', description: 'New', actions: ['users:read_own'], resource_type: 'users', conditions: null, is_active: true }, changed_fields: ['description'], changed_by: 'admin@example.com', change_reason: null, created_at: '2026-02-01T00:00:00Z' },
    ]);
    mock.onPost('/authorization/policies/report_viewer/history/2/rollback').reply(200, SAMPLE_POLICIES[0]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    await user.click(await screen.findByRole('button', { name: 'Roll back' }));
    const rollbackDialog = await screen.findByRole('alertdialog');
    expect(rollbackDialog).toBeInTheDocument();
    await user.click(within(rollbackDialog).getByRole('button', { name: 'Roll back' }));

    await waitFor(() => expect(mock.history.post).toHaveLength(1));
  });

  it('does not autofocus the policies:read action copy control when details opens', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/policies/report_viewer/history').reply(200, []);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'View' }));

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('tab', { name: 'Details' })).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Copy users:read_own' })).not.toHaveFocus();
  });

  it('shows how many users will lose access in the delete confirmation', async () => {
    seed(['policies:read', 'policies:delete', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], is_active: false }]);
    mock.onGet('/authorization/policies/report_viewer/holders').reply(200, [
      { email: 'alice@example.com', name: 'Alice Admin', role: 'admin', assigned_at: '2026-02-01T00:00:00Z', assigned_by: 'system' },
      { email: 'bob@example.com', name: 'Bob Builder', role: 'user', assigned_at: '2026-02-02T00:00:00Z', assigned_by: 'system' },
    ]);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));

    expect(await screen.findByText(/2 users currently hold this policy and will lose the access it grants\./)).toBeInTheDocument();
  });
});
