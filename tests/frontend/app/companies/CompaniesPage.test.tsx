import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import CompaniesPage from '@app/companies/CompaniesPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test User',
    email: 'user@example.com',
    role: 'user',
    permissions,
    has_password: true,
    created_at: '2026-01-15T00:00:00Z',
    active_sessions: 1,
  });
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChakraProvider value={defaultSystem}>
        <MemoryRouter>
          <CompaniesPage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

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
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: 1, group_root_id: 1 },
    ]);

    renderPage();

    expect(await screen.findByText('Jio Platforms')).toBeInTheDocument();
    expect(screen.getByText('JIO.NS')).toBeInTheDocument();
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

  it('shows the "Add company" action and submits a create request for a user with company:create', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onPost('/companies/').reply(201, {
      id: 3,
      name: 'Reliance Retail Ventures',
      ticker: 'RRVL.NS',
      parent_company_id: null,
      group_root_id: 3,
    });

    renderPage();

    const addButton = await screen.findByRole('button', { name: 'Add company' });
    await user.click(addButton);

    await user.type(screen.getByPlaceholderText('Company name (e.g. Jio Platforms)'), 'Reliance Retail Ventures');
    await user.type(screen.getByPlaceholderText('Ticker (e.g. JIO.NS)'), 'RRVL.NS');
    await user.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      expect(mock.history.post).toHaveLength(1);
    });
    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({
      name: 'Reliance Retail Ventures',
      ticker: 'RRVL.NS',
    });
  });

  it('autofills the company name from the ticker lookup when the name field is left blank', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/lookup/RRVL.NS').reply(200, { ticker: 'RRVL.NS', name: 'Reliance Retail Ventures' });

    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Ticker (e.g. JIO.NS)'), 'RRVL.NS');
    await user.tab(); // blur the ticker field to trigger the lookup

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Company name (e.g. Jio Platforms)')).toHaveValue('Reliance Retail Ventures');
    });
    expect(mock.history.get.some((r) => r.url === '/companies/lookup/RRVL.NS')).toBe(true);
  });

  it('does not overwrite a manually entered company name with the ticker lookup', async () => {
    const user = userEvent.setup();
    seed(['company:read', 'company:create']);
    mock.onGet('/companies/').reply(200, []);
    mock.onGet('/companies/lookup/RRVL.NS').reply(200, { ticker: 'RRVL.NS', name: 'Reliance Retail Ventures' });

    renderPage();

    await user.click(await screen.findByRole('button', { name: 'Add company' }));
    await user.type(screen.getByPlaceholderText('Company name (e.g. Jio Platforms)'), 'My Custom Name');
    await user.type(screen.getByPlaceholderText('Ticker (e.g. JIO.NS)'), 'RRVL.NS');
    await user.tab();

    // No lookup call is made at all: the name field was already non-empty.
    expect(mock.history.get.some((r) => r.url === '/companies/lookup/RRVL.NS')).toBe(false);
    expect(screen.getByPlaceholderText('Company name (e.g. Jio Platforms)')).toHaveValue('My Custom Name');
  });

  it('hides the row-level "Edit" action for a user without company:update', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();

    await screen.findByText('Jio Platforms');
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
  });

  it('opens the row-level "Edit" form pre-filled and submits an update via PATCH', async () => {
    seed(['company:read', 'company:update']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: null, group_root_id: 2 },
    ]);
    mock.onPatch('/companies/2').reply(200, {
      id: 2,
      name: 'Jio Platforms Ltd',
      ticker: 'JIO.NS',
      parent_company_id: null,
      group_root_id: 2,
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const nameInput = screen.getByDisplayValue('Jio Platforms');
    expect(screen.getByDisplayValue('JIO.NS')).toBeInTheDocument();

    await user.clear(nameInput);
    await user.type(nameInput, 'Jio Platforms Ltd');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mock.history.patch).toHaveLength(1));
    expect(JSON.parse(mock.history.patch[0].data)).toMatchObject({
      name: 'Jio Platforms Ltd',
      ticker: 'JIO.NS',
      parent_company_id: null,
    });
    // Form closes on success (same close path as create); the list itself
    // refetches via query invalidation, covered separately by the "renders
    // only the companies the backend returns" test, not re-asserted here.
    await waitFor(() => expect(screen.queryByDisplayValue('Jio Platforms Ltd')).toBeNull());
  });

  it('closes the edit form without submitting when "Cancel" is clicked', async () => {
    seed(['company:read', 'company:update']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    expect(screen.getByDisplayValue('Jio Platforms')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByDisplayValue('Jio Platforms')).toBeNull();
    expect(mock.history.patch).toHaveLength(0);
  });

  it('hides the row-level "Delete" action for a user without company:delete', async () => {
    seed(['company:read']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: null, group_root_id: 2 },
    ]);

    renderPage();

    await screen.findByText('Jio Platforms');
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('deletes a company after confirming in the ConfirmDialog', async () => {
    seed(['company:read', 'company:delete']);
    mock.onGet('/companies/').reply(200, [
      { id: 2, name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: null, group_root_id: 2 },
    ]);
    mock.onDelete('/companies/2').reply(204);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(await screen.findByText(/Delete Jio Platforms\?/)).toBeInTheDocument();

    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('sends the DELETE request when deleting a company fails (e.g. it has subsidiaries)', async () => {
    seed(['company:read', 'company:delete']);
    mock.onGet('/companies/').reply(200, [
      { id: 1, name: 'Reliance Industries', ticker: 'RELIANCE.NS', parent_company_id: null, group_root_id: 1 },
    ]);
    mock.onDelete('/companies/1').reply(400, {
      detail: "Cannot delete 'Reliance Industries': it has 2 subsidiary company(ies). Delete or reassign those first.",
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
