import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, seed, renderPage, CATALOG, USAGE } from './permissionsPageTestSupport';

// PermissionsPage: resource-type grouping, expand/collapse, and the
// Expand all / Collapse all controls. Filters and the details dialog live
// in their own sibling files - split out of one 408-line file, see
// AGENTS.md's ~350-line target.

describe('PermissionsPage: groups', () => {
  beforeEach(() => {
    mock.reset();
    seed(['permissions:read']);
  });

  it('lists catalog entries grouped by resource type, collapsed by default', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();

    expect(await screen.findByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Security Audit')).toBeInTheDocument();
    // Collapsed: no action rows rendered yet.
    expect(screen.queryByText('Read own users')).toBeNull();
  });

  it('shows stable resource-type card skeletons while the catalog loads', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(() => new Promise(() => {}));
    mock.onGet('/authorization/permissions/catalog/usage').reply(() => new Promise(() => {}));

    renderPage();

    expect(screen.getByRole('status', { name: 'Loading...' })).toBeInTheDocument();
    expect(screen.getByRole('status').querySelectorAll('[data-slot="skeleton"]')).toHaveLength(25);
  });

  it('shows verified catalog statistics while holder usage is still loading', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(() => new Promise(() => {}));

    renderPage();

    expect(await screen.findByText('Users')).toBeInTheDocument();
    expect(within(screen.getByRole('button', { name: 'Actions' })).getByText('3')).toBeInTheDocument();
    expect(within(screen.getByLabelText('Resource types')).getByText('2')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Unused/ })).toBeDisabled();
  });

  it('expands a group on click and shows its rows, including the Held by column', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByText('Users'));

    expect(await screen.findByText('Read own users')).toBeInTheDocument();
    expect(screen.getByText('Delete any users')).toBeInTheDocument();
    // heldByCount_other: "{{count}} users" for the 5-user row.
    expect(screen.getByText('5 users')).toBeInTheDocument();
    expect(screen.getByText('0 direct · 1 via policy')).toBeInTheDocument();
    expect(screen.getByText('1 direct · 0 via policy')).toBeInTheDocument();
  });

  it('expands and collapses a group when its metadata row area is clicked', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();
    const actionCount = await screen.findByText('2 actions');

    await user.click(actionCount);
    expect(await screen.findByText('Read own users')).toBeInTheDocument();

    await user.click(actionCount);
    expect(screen.queryByText('Read own users')).toBeNull();
  });

  it('provides an accessible disclosure control for each resource type', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();
    const usersToggle = await screen.findByRole('button', { name: /^Users/ });

    expect(usersToggle).toHaveAttribute('aria-expanded', 'false');
    const panelId = usersToggle.getAttribute('aria-controls');
    expect(panelId).toBeTruthy();
    expect(document.getElementById(panelId!)).toHaveAttribute('hidden');

    usersToggle.focus();
    await user.keyboard('{Enter}');

    expect(usersToggle).toHaveAttribute('aria-expanded', 'true');
    expect(document.getElementById(panelId!)).not.toHaveAttribute('hidden');
    expect(await screen.findByText('Read own users')).toBeInTheDocument();

    await user.keyboard(' ');
    expect(usersToggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Read own users')).toBeNull();
  });

  it('Expand all opens every group and Collapse all closes them, both staying enabled throughout', async () => {
    // Regression for review bugs #3/#4: these buttons must stay visible/
    // enabled (not vanish), and Collapse all must work even right after a
    // search/filter forced every group open.
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();
    await screen.findByText(/^Users$/);

    const expandAll = screen.getByRole('button', { name: 'Expand all' });
    const collapseAll = screen.getByRole('button', { name: 'Collapse all' });
    expect(expandAll).toBeEnabled();

    await user.click(expandAll);
    expect(await screen.findByText('Read own users')).toBeInTheDocument();
    expect(collapseAll).toBeEnabled();

    await user.click(collapseAll);
    await waitFor(() => expect(screen.queryByText('Read own users')).toBeNull());
  });
});
