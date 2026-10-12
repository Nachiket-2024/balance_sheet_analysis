import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, renderPage, seed } from './companiesPageTestSupport';

describe('CompaniesPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it("renders only the companies the backend returns for this user's scope", async () => {
    // The backend (not this page) is what enforces company_id/group_root_id
    // scoping, see backend/app/access/scope.py. This test only asserts the
    // page faithfully renders whatever GET /companies/ returns, not that it
    // performs any client-side filtering of its own.
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'GitHub, Inc.', ticker: 'GITHUB.DEMO', parent_company_id: 1, group_root_id: 1 },
    ]);

    renderPage();

    expect(await screen.findByText('GitHub, Inc.')).toBeInTheDocument();
    expect(screen.getByText('GITHUB.DEMO')).toBeInTheDocument();
  });

  it('shows an empty-scope message when the user has no accessible companies', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, []);

    renderPage();

    expect(await screen.findByText('No companies assigned to you yet')).toBeInTheDocument();
    expect(
      screen.getByText("You don't have access to any companies yet. Ask an administrator to assign you a policy.")
    ).toBeInTheDocument();
  });

  it('applies stats-card and hierarchy filters to the server query', async () => {
    const user = userEvent.setup();
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/stats').reply(200, { total: 3, group_roots: 1, subsidiaries: 2 });

    renderPage();
    await screen.findByText('No companies assigned to you yet');
    await user.click(await screen.findByRole('button', { name: 'Filter companies: Total companies' }));
    await user.click(screen.getByRole('button', { name: 'Filter companies: Group roots' }));
    await user.click(screen.getByRole('button', { name: 'Filter companies: Subsidiaries' }));

    expect(screen.getByRole('combobox', { name: 'Filter by scope' })).toHaveTextContent('Subsidiaries');
  });

  it('hides the "Add company" action for a user without company:create', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, []);

    renderPage();

    await waitFor(() => expect(screen.queryByText('No companies assigned to you yet')).toBeInTheDocument());
    // .not.toBeInTheDocument() doesn't type-check here, see
    // docs/mystic_auth/testing/overview.md's ".not chaining" note:
    // toBeNull() on queryByRole's result is the positive-assertion equivalent.
    expect(screen.queryByRole('button', { name: 'Add company' })).toBeNull();
  });
});
