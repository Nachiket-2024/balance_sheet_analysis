import { describe, it, expect, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, seed, renderPage, CATALOG, USAGE } from './permissionsPageTestSupport';

// PermissionsPage: search, resource-type filter, and the Destructive/Unused
// quick filters. Group behavior and the details dialog live in their own
// sibling files - split out of one 408-line file, see AGENTS.md's
// ~350-line target.

describe('PermissionsPage: filters', () => {
  beforeEach(() => {
    mock.reset();
    seed(['permissions:read']);
  });

  it('the resource-type filter is built from the loaded catalog, not a hardcoded list', async () => {
    // Regression for .project/permissions-page-review.md bug #1: a fork's
    // own resource type (here, an "invoices" entry the fixed 5-type
    // AUTHORIZATION_RESOURCE_TYPES list has never heard of) must still be
    // selectable.
    mock.onGet('/authorization/permissions/catalog').reply(200, [
      ...CATALOG,
      { action: 'invoices:read', resource_type: 'invoices', description: 'Read invoices.' },
    ]);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    await screen.findByText('Users');

    const select = (await screen.findByLabelText('Filter by resource type', {
      selector: 'select',
    })) as HTMLSelectElement;
    const values = [...select.options].map((o) => o.value);
    expect(values).toContain('invoices');
  });

  it('filters to destructive actions via the quick filter, matching isDestructiveAction', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('radio', { name: /Destructive/ }));

    // users:delete_any is destructive and stays; users:read_own's group
    // should no longer render at all once its only entry is filtered out.
    expect(await screen.findByText(/^Users$/)).toBeInTheDocument();
    expect(screen.queryByText('Security Audit')).toBeNull();
  });

  it('filters to unused actions via the quick filter, using usage data', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('radio', { name: /^Unused/ }));

    // Only security_audit:read has total_user_count 0.
    expect(await screen.findByText('Security Audit')).toBeInTheDocument();
    expect(screen.queryByText(/^Users$/)).toBeNull();
  });

  it('Clear filters resets search, resource type, and quick filter', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('radio', { name: /Destructive/ }));
    expect(screen.queryByText('Security Audit')).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(await screen.findByText('Security Audit')).toBeInTheDocument();
  });

  it('renders search and resource-type filter chips from translated labels', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.type(await screen.findByPlaceholderText('Search by action or description...'), 'policies');
    await user.selectOptions(
      screen.getByLabelText('Filter by resource type', { selector: 'select' }),
      'users',
    );

    expect(await screen.findByText('Search: policies')).toBeInTheDocument();
    expect(screen.getByText('Resource type: Users')).toBeInTheDocument();
  });

  it('shows a clear-filters empty state when the search matches nothing', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.type(await screen.findByPlaceholderText('Search by action or description...'), 'nonexistent_action_xyz');

    expect(await screen.findByText('No permissions match these filters')).toBeInTheDocument();
  });
});
