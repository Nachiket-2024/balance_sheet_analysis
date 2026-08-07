import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import { MemoryRouter } from 'react-router';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import { useAuthStore } from '@/store/authStore';
import PoliciesPage from '@/policies/PoliciesPage';

const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

function seed(permissions: string[]) {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: 'Test Admin',
    email: 'admin@example.com',
    role: 'admin',
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
          <PoliciesPage />
        </MemoryRouter>
      </ChakraProvider>
    </QueryClientProvider>
  );
}

const SAMPLE_POLICIES = [
  {
    id: 1,
    name: 'self_service',
    description: 'Basic self-service access',
    actions: ['users:read_own'],
    resource_type: 'users',
    conditions: null,
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    created_by: null,
  },
];

describe('PoliciesPage', () => {
  beforeEach(() => {
    mock.reset();
  });

  it('lists policies returned by the backend', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    expect(await screen.findByText('self_service')).toBeInTheDocument();
  });

  it('hides the Create Policy button when the caller lacks policies:create', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    await screen.findByText('self_service');
    expect(screen.queryByRole('button', { name: 'Create Policy' })).toBeNull();
  });

  it('shows the Create Policy button and opens the form when the caller holds policies:create', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    const createButton = await screen.findByRole('button', { name: 'Create Policy' });
    await userEvent.click(createButton);

    expect(screen.getByPlaceholderText('e.g. document_reviewer')).toBeInTheDocument();
  });

  it('hides Edit/Delete row actions for a caller with only policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    await screen.findByText('self_service');
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('creates a policy via the form, submitting the expected payload, and closes the dialog on success', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onPost('/authorization/policies').reply(201, {
      id: 2,
      name: 'document_reviewer',
      description: 'Can review documents',
      actions: ['documents:review'],
      resource_type: 'documents',
      conditions: null,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      created_by: 'admin@example.com',
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'document_reviewer');
    await user.type(screen.getByPlaceholderText('e.g. documents:view, documents:edit'), 'documents:review');
    await user.type(screen.getByPlaceholderText('e.g. "documents" or "*" for any'), 'documents');
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      name: 'document_reviewer',
      description: '',
      actions: ['documents:review'],
      resource_type: 'documents',
      conditions: undefined,
    });
  });

  it('shows a local validation error and does not submit when Conditions is invalid JSON', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'broken_policy');
    await user.type(screen.getByPlaceholderText('e.g. documents:view, documents:edit'), 'documents:view');
    await user.type(screen.getByPlaceholderText('e.g. "documents" or "*" for any'), 'documents');
    await user.type(screen.getByPlaceholderText('e.g. { "self_only": true }'), '{{ not valid json');
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    expect(await screen.findByText('Conditions must be valid JSON')).toBeInTheDocument();
    expect(mock.history.post.length).toBe(0);
  });

  it('shows an error message in the dialog when creating a policy fails', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onPost('/authorization/policies').reply(500);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'broken_policy');
    await user.type(screen.getByPlaceholderText('e.g. documents:view, documents:edit'), 'documents:view');
    await user.type(screen.getByPlaceholderText('e.g. "documents" or "*" for any'), 'documents');
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    expect(await screen.findByText('Failed to create policy')).toBeInTheDocument();
  });

  it('opens the edit form pre-filled and submits an update via PUT', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onPut('/authorization/policies/self_service').reply(200, {
      ...SAMPLE_POLICIES[0],
      description: 'Updated description',
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    expect(screen.getByDisplayValue('self_service')).toBeInTheDocument();

    const descriptionInput = screen.getByDisplayValue('Basic self-service access');
    await user.clear(descriptionInput);
    await user.type(descriptionInput, 'Updated description');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toMatchObject({ description: 'Updated description' });
  });

  it('deletes a policy after confirming in the ConfirmDialog', async () => {
    seed(['policies:read', 'policies:delete']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onDelete('/authorization/policies/self_service').reply(204);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(await screen.findByText(/Delete "self_service"\?/)).toBeInTheDocument();

    const confirmButtons = screen.getAllByRole('button', { name: 'Delete' });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(mock.history.delete.length).toBe(1));
  });

  it('prompts to discard unsaved changes when closing a dirty form', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'draft_policy');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(await screen.findByText('Discard unsaved changes?')).toBeInTheDocument();

    // Cancelling the discard-confirm dialog must leave the form dialog open with the typed value
    // intact. Both dialogs are mounted at once here, each with their own "Cancel" button - the
    // discard-confirm's is the last one rendered.
    const cancelButtons = screen.getAllByRole('button', { name: 'Cancel' });
    await user.click(cancelButtons[cancelButtons.length - 1]);
    expect(screen.getByDisplayValue('draft_policy')).toBeInTheDocument();
  });
});
