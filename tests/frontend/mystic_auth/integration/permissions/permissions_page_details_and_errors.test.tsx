import { describe, it, expect, beforeEach } from 'vitest';
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, seed, renderPage, CATALOG, USAGE } from './permissionsPageTestSupport';

// PermissionsPage: the row details dialog and load-failure/access-denied
// states. Group behavior and filters live in their own sibling files -
// split out of one 408-line file, see AGENTS.md's ~350-line target.

describe('PermissionsPage: details dialog and errors', () => {
  beforeEach(() => {
    mock.reset();
    seed(['permissions:read']);
  });

  it('opens the details dialog with policies and held-by summary for a row', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);
    seed(['permissions:read', 'policies:read', 'users:list_all']);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByText('Users'));
    // Rows sort alphabetically by action: users:delete_any, then users:read_own.
    await user.click((await screen.findAllByRole('button', { name: 'View details' }))[1]);

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('self_service')).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Open policy details for self_service' })).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'View users with Via policy access' })).toHaveAttribute(
      'href',
      '/users?permission=users%3Aread_own&permission_source=policy',
    );
  });

  it('links direct-grant holders to the matching direct-source Users filter', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);
    seed(['permissions:read', 'users:list_all']);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByText('Users'));
    await user.click((await screen.findAllByRole('button', { name: 'View details' }))[0]);

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('link', { name: 'View users with Direct grants access' })).toHaveAttribute(
      'href',
      '/users?permission=users%3Adelete_any&permission_source=direct',
    );
  });

  it('keeps policy names read-only when the caller cannot read policies', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByText('Users'));
    await user.click((await screen.findAllByRole('button', { name: 'View details' }))[1]);

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('self_service')).toBeInTheDocument();
    expect(within(dialog).queryByRole('link', { name: /self_service/ })).toBeNull();
  });

  it('shows a destructive banner in the dialog for a destructive action', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByText('Users'));
    const viewButtons = await screen.findAllByRole('button', { name: 'View details' });
    await user.click(viewButtons[0]); // users:delete_any

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/can't be undone easily/)).toBeInTheDocument();
  });

  it('shows a Retry button on load failure, which refetches on click', async () => {
    mock.onGet('/authorization/permissions/catalog').replyOnce(500);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, []);

    renderPage();
    const user = userEvent.setup();

    expect(await screen.findByText('Failed to load the permission catalog')).toBeInTheDocument();

    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText(/^Users$/)).toBeInTheDocument();
  });

  it('keeps the catalog usable when holder information fails and retries only that data', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').replyOnce(500);

    renderPage();
    const user = userEvent.setup();

    expect(await screen.findByText('Could not load holder information')).toBeInTheDocument();
    expect(screen.getByText('Policy and direct-grant counts are temporarily unavailable.')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /In a policy/ })).toBeDisabled();
    expect(screen.getByRole('radio', { name: /Unused/ })).toBeDisabled();
    expect(screen.getByText('Users')).toBeInTheDocument();

    mock.onGet('/authorization/permissions/catalog/usage').reply(200, USAGE);
    await user.click(screen.getByRole('button', { name: 'Retry holder information' }));

    expect(await screen.findByRole('radio', { name: /In a policy/ })).toBeEnabled();
    expect(screen.queryByText('Could not load holder information')).toBeNull();
  });

  it('explains when catalog access is denied after the page starts loading', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(403);
    mock.onGet('/authorization/permissions/catalog/usage').reply(200, []);

    renderPage();

    expect(await screen.findByText(/permission catalog is no longer available/i)).toBeInTheDocument();
  });

  it('explains when holder information access is denied', async () => {
    mock.onGet('/authorization/permissions/catalog').reply(200, CATALOG);
    mock.onGet('/authorization/permissions/catalog/usage').reply(403);

    renderPage();

    expect(await screen.findByText(/holder information is no longer available/i)).toBeInTheDocument();
  });
});
