import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen, act, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { toaster } from '@/ui/toaster/toasterInstance';

import { mock, seed, renderPage, PERMISSION_CATALOG, SAMPLE_POLICIES } from './policiesPageFollowUpTestSupport';

// PoliciesPage follow-up flows: protected-policy guards, the
// policies:create-only restricted view, and the per-action toggle. Dialog
// tabs, rollback, and the delete confirmation live in their own sibling
// file - split out of one 408-line file, see AGENTS.md's ~350-line target.

describe('PoliciesPage follow-up flows: guards', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    await act(async () => {
      toaster.remove();
    });
  });

  it('disables status changes and hides Delete for an active protected policy', async () => {
    seed(['policies:read', 'policies:update', 'policies:delete']);
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], name: 'self_service', is_active: true }]);

    renderPage();

    expect(await screen.findByRole('switch', { name: 'Deactivate' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('keeps grant-guarded status and delete controls visible but disabled', async () => {
    seed(['policies:read', 'policies:update', 'policies:delete']);
    mock.onGet('/authorization/policies').reply(200, [{
      ...SAMPLE_POLICIES[0],
      is_active: false,
      actions: ['users:delete_any'],
    }]);

    renderPage();

    expect(await screen.findByRole('switch', { name: 'Activate' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled();
  });

  it('blocks policy deletion until holder impact can be confirmed', async () => {
    seed(['policies:read', 'policies:delete', 'users:read_own']);
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], is_active: false }]);
    mock.onGet('/authorization/policies/report_viewer/holders').reply(500);

    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Delete' }));

    expect(await screen.findByText(/policy holders could not be checked/i)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Delete' }).at(-1)).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(mock.history.get.filter((request) => request.url?.endsWith('/holders'))).toHaveLength(2);
  });

  it('keeps Delete hidden while the protected baseline policy is active', async () => {
    seed(['policies:read', 'policies:update', 'policies:delete']);
    mock.onGet('/authorization/policies').reply(200, [{ ...SAMPLE_POLICIES[0], name: 'self_service', is_active: true }]);

    renderPage();

    await screen.findByText('Protected');
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('shows a restricted-view notice and a standalone Create button for a caller with only policies:create', async () => {
    seed(['policies:create']);
    renderPage();

    expect(await screen.findByText(/create policies, but you don't have permission to view/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create Policy' })).toBeInTheDocument();
    expect(mock.history.get.filter((request) => request.url === '/authorization/policies')).toHaveLength(0);
  });

  it('opens the create form from the restricted view for a policies:create-only caller', async () => {
    seed(['policies:create']);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));

    expect(screen.getByPlaceholderText('e.g. document_reviewer')).toBeInTheDocument();
  });

  it('describes policy recipients without implying an admin role', async () => {
    seed(['policies:create']);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));

    expect(screen.getByText(/authorized operator chooses a policy to assign/i)).toBeInTheDocument();
    expect(screen.getByText(/policy holders it is intended for/i)).toBeInTheDocument();
    expect(screen.queryByText(/shown to admins/i)).toBeNull();
  });

  it('does not show the restricted-view notice when the caller holds policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    renderPage();

    await screen.findByText('report_viewer');
    expect(screen.queryByText(/don't have permission to view/i)).toBeNull();
  });

  it('keeps the protected system policy edit action visible but disabled', async () => {
    seed(['policies:read', 'policies:update']);
    const systemSuperuser = { ...SAMPLE_POLICIES[0], id: 9, name: 'system_superuser', description: 'Full access', actions: ['users:read_own', 'policies:read'], resource_type: '*' };
    mock.onGet('/authorization/policies').reply(200, [systemSuperuser]);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    renderPage();
    expect(await screen.findByRole('button', { name: 'Edit' })).toBeDisabled();
  });

  it('toggles a policy action when its switch is clicked directly', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    mock.onPut('/authorization/policies/report_viewer').reply(200, SAMPLE_POLICIES[0]);
    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(screen.getByRole('tab', { name: /^Actions/ }));
    const actionSwitch = await screen.findByRole('switch', { name: 'Read own users' });
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Read own users' })).toBeChecked());
    await user.click(actionSwitch);
    expect(actionSwitch).not.toBeChecked();
    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ actions: [] });
    // Query the actionable control directly. The toast intentionally has a
    // finite Undo window, so waiting for the title first makes this test
    // race the same expiry a user would have in a busy CI worker.
    const undo = await screen.findByRole('button', { name: 'Undo' });
    expect(screen.getByText('Removed Read own users from "report_viewer".')).toBeInTheDocument();
    fireEvent.click(undo);
    await waitFor(() => expect(mock.history.put.length).toBe(2));
    expect(JSON.parse(mock.history.put[1].data)).toEqual({ actions: ['users:read_own'] });
    await waitFor(() => expect(screen.getByRole('switch', { name: 'Read own users' })).toBeChecked());
  });
});
