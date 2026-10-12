import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { mock, renderPage, seed } from './companiesPageTestSupport';

describe('CompaniesPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('shows the "Add company" action and submits a create request for a user with company:create', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onPost('/companies/').reply(201, {
      id: 3,
      name: 'LinkedIn Corporation',
      ticker: 'LINKEDIN.DEMO',
      parent_company_id: null,
      group_root_id: 3,
    });

    renderPage();

    const addButton = await screen.findByRole('button', { name: 'Add company' });
    await user.click(addButton);

    await user.type(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)'), 'LinkedIn Corporation');
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'LINKEDIN.DEMO');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      expect(mock.history.post).toHaveLength(1);
    });
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({
      name: 'LinkedIn Corporation',
      ticker: 'LINKEDIN.DEMO',
    });
  });

  it('renders the create error returned by the backend', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onPost('/companies/').reply(400, { detail: 'Ticker is already registered' });

    renderPage();
    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)'), 'Existing Co');
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'MSFT');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ticker is already registered');
  });

  it('autofills the company name from the ticker lookup when the name field is left blank', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/lookup/MSFT').reply(200, { ticker: 'MSFT', name: 'Microsoft Corporation' });

    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'MSFT');
    await user.tab(); // blur the ticker field to trigger the lookup

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)')).toHaveValue('Microsoft Corporation');
    });
    expect(mock.history.get.some((r) => r.url === '/companies/lookup/MSFT')).toBe(true);
  });

  it('blocks creating a duplicate ticker and displays the server warning', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply((config) => {
      if (config.params?.search === 'MSFT') {
        return [200, [{ id: 11, name: 'Microsoft Corporation', ticker: 'MSFT' }]];
      }
      return [200, []];
    });

    renderPage();
    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'MSFT');

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create' })).toBeDisabled();
  });

  it('does not overwrite a manually entered company name with the ticker lookup', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/lookup/MSFT').reply(200, { ticker: 'MSFT', name: 'Microsoft Corporation' });

    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)'), 'My Custom Name');
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'MSFT');
    await user.tab();

    // No lookup call is made at all: the name field was already non-empty.
    expect(mock.history.get.some((r) => r.url === '/companies/lookup/MSFT')).toBe(false);
    expect(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)')).toHaveValue('My Custom Name');
  });

  it('loads ticker suggestions and fills both ticker and company name when selected', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/search/LI').reply(200, {
      query: 'LI',
      results: [{ ticker: 'LINKEDIN.DEMO', name: 'LinkedIn Corporation', exchange: 'DEMO' }],
    });

    renderPage();
    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Ticker (e.g. MSFT)'), 'LI');

    const suggestion = await screen.findByText('LINKEDIN.DEMO · DEMO', {}, { timeout: 2_000 });
    await user.click(suggestion);

    expect(screen.getByPlaceholderText('Ticker (e.g. MSFT)')).toHaveValue('LINKEDIN.DEMO');
    expect(screen.getByPlaceholderText('Company name (e.g. Microsoft Corporation)')).toHaveValue('LinkedIn Corporation');
  });
});
