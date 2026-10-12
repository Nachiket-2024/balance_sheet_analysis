import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, renderPage, seed } from './companiesPageTestSupport';

describe('CompaniesPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('hides the row-level "Edit" action for a user without company:update', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();

    await screen.findByText('GitHub, Inc.');
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
  });

  it('opens the row-level "Edit" form pre-filled and submits an update via PATCH', async () => {
    seed(['company:read', 'company:update']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);
    mock.onPatch('/companies/2').reply(200, {
      id: 2,
      name: 'GitHub, Inc. Ltd',
      ticker: 'GITHUB.DEMO',
      parent_company_id: null,
      group_root_id: 2,
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const nameInput = screen.getByDisplayValue('GitHub, Inc.');
    expect(screen.getByDisplayValue('GITHUB.DEMO')).toBeInTheDocument();

    await user.clear(nameInput);
    await user.type(nameInput, 'GitHub, Inc. Ltd');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mock.history.patch).toHaveLength(1));
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({
      name: 'GitHub, Inc. Ltd',
      ticker: 'GITHUB.DEMO',
      parent_company_id: null,
    });
    // Form closes on success (same close path as create); the list itself
    // refetches via query invalidation, covered separately by the "renders
    // only the companies the backend returns" test, not re-asserted here.
    await waitFor(() => expect(screen.queryByDisplayValue('GitHub, Inc. Ltd')).toBeNull());
  });

  it('closes the edit form without submitting when "Cancel" is clicked', async () => {
    seed(['company:read', 'company:update']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    expect(screen.getByDisplayValue('GitHub, Inc.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByDisplayValue('GitHub, Inc.')).toBeNull();
    expect(mock.history.patch).toHaveLength(0);
  });

  it('cancels a pending company deletion without sending a request', async () => {
    seed(['company:read', 'company:delete']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByText(/Delete GitHub, Inc\.\?/)).toBeNull();
    expect(mock.history.delete).toHaveLength(0);
  });

  it('hides the row-level "Delete" action for a user without company:delete', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();

    await screen.findByText('GitHub, Inc.');
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('deletes a company after confirming in the ConfirmDialog', async () => {
    seed(['company:read', 'company:delete']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: null, group_root_id: 2 },
    ]);
    mock.onDelete('/companies/2').reply(204);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(await screen.findByText(/Delete GitHub, Inc\.\?/)).toBeInTheDocument();

    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('sends the DELETE request when deleting a company fails (e.g. it has subsidiaries)', async () => {
    seed(['company:read', 'company:delete']);
    mock.onGet('/companies/').reply(200, [
      { id: 1, name: 'Microsoft Corporation', ticker: 'MSFT', parent_company_id: null, group_root_id: 1 },
    ]);
    mock.onDelete('/companies/1').reply(400, {
      detail: "Cannot delete 'Microsoft Corporation': it has 2 subsidiary company(ies). Delete or reassign those first.",
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    // Failure surfaces via a toast, not inline text, so just confirm the DELETE fired.
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });
});
