import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { toaster } from '@/ui/toaster/toasterInstance';

import { mock, seed, renderPage, PERMISSION_CATALOG, SAMPLE_POLICIES } from './policiesPageTestSupport';

// PoliciesPage: the list, expand/collapse, and the create/edit form
// (including conditions JSON validation). Status toggles, delete, and undo
// live in their own sibling file - split out of one 395-line file, see
// AGENTS.md's ~350-line target.

describe('PoliciesPage: list and form', () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton that outlives each test's render
    // tree; clear it so a leftover toast (every switch toggle creates one,
    // even in tests that don't mount <Toaster/>) can't leak into the next
    // test - see users_page_bulk_actions.test.tsx's identical cleanup.
    await act(async () => {
      toaster.remove();
    });
  });

  it('lists policies returned by the backend', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    expect(await screen.findByText('report_viewer')).toBeInTheDocument();
  });

  it('hides the Create Policy button when the caller lacks policies:create', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    await screen.findByText('report_viewer');
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

  it('limits policy descriptions and shows the live character count', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);

    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Create Policy' }));

    expect(screen.getByLabelText('Description')).toHaveAttribute('maxLength', '160');
    expect(screen.getByText('0/160 characters')).toBeInTheDocument();
  });

  it('hides Edit/Delete row actions for a caller with only policies:read', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();

    await screen.findByText('report_viewer');
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  it('expands a policy from the labelled header control with keyboard access', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();
    const user = userEvent.setup();
    const expandButton = await screen.findByRole('button', { name: 'Expand policy report_viewer' });

    expect(expandButton).toHaveAttribute('aria-expanded', 'false');
    await user.click(expandButton);

    expect(expandButton).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Read own users')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Collapse policy report_viewer' })).toHaveFocus();
  });

  it('expands and collapses when the policy header row is clicked', async () => {
    seed(['policies:read']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);

    renderPage();
    const user = userEvent.setup();
    const policyName = await screen.findByText('report_viewer');
    const expandButton = screen.getByRole('button', { name: 'Expand policy report_viewer' });

    await user.click(policyName);
    expect(expandButton).toHaveAttribute('aria-expanded', 'true');

    await user.click(policyName);
    expect(expandButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('creates a policy via the form, submitting the expected payload, and closes the dialog on success', async () => {
    seed(['policies:read', 'policies:create', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    mock.onPost('/authorization/policies').reply(201, {
      id: 2,
      name: 'document_reviewer',
      description: 'Can review documents',
      actions: ['policies:update'],
      resource_type: 'policies',
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
    // Resource type is chosen on the Basics tab before actions - the
    // Actions tab's options are scoped to whichever resource type is
    // currently selected (see PolicyFormDialog's actionOptions).
    await user.selectOptions(screen.getByLabelText('Resource type', { selector: 'select' }), 'policies');
    await user.click(screen.getByRole('tab', { name: /^Actions/ }));
    await user.click(await screen.findByText("Edit an existing policy's fields."));
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      name: 'document_reviewer',
      description: '',
      actions: ['policies:update'],
      resource_type: 'policies',
      conditions: undefined,
    });
  });

  it('shows a local validation error and does not submit when Conditions is invalid JSON', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'broken_policy');
    await user.selectOptions(screen.getByLabelText('Resource type', { selector: 'select' }), 'policies');
    // Conditions are tucked behind a checkbox toggle on the Basics tab.
    await user.click(screen.getByRole('checkbox', { name: 'Add conditions (optional, for advanced setups)' }));
    await user.type(screen.getByPlaceholderText('e.g. { "self_only": true }'), '{{ not valid json');
    await user.click(screen.getByRole('tab', { name: /^Actions/ }));
    await user.click(await screen.findByText('Read/list policies.'));
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    expect(await screen.findByText('Conditions must be valid JSON')).toBeInTheDocument();
    expect(mock.history.post.length).toBe(0);
  });

  it('shows the invalid-JSON error live as the admin types, before submitting', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.click(screen.getByRole('checkbox', { name: 'Add conditions (optional, for advanced setups)' }));

    // No error yet with the textarea empty.
    expect(screen.queryByText('Conditions must be valid JSON')).toBeNull();

    await user.type(screen.getByPlaceholderText('e.g. { "self_only": true }'), '{{ not valid json');

    // Shows up without ever clicking Create policy.
    expect(await screen.findByText('Conditions must be valid JSON')).toBeInTheDocument();
    expect(mock.history.post.length).toBe(0);

    // Fixing it to valid JSON (but not an object) still errors...
    await user.clear(screen.getByPlaceholderText('e.g. { "self_only": true }'));
    await user.type(screen.getByPlaceholderText('e.g. { "self_only": true }'), '"just a string"');
    expect(await screen.findByText('Conditions must be valid JSON')).toBeInTheDocument();

    // ...but a real JSON object clears it.
    fireEvent.change(screen.getByPlaceholderText('e.g. { "self_only": true }'), {
      target: { value: '{"self_only": true}' },
    });
    await waitFor(() => expect(screen.queryByText('Conditions must be valid JSON')).toBeNull());
  });

  it('shows an error message in the dialog when creating a policy fails', async () => {
    seed(['policies:read', 'policies:create']);
    mock.onGet('/authorization/policies').reply(200, []);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    mock.onPost('/authorization/policies').reply(500);

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Create Policy' }));
    await user.type(screen.getByPlaceholderText('e.g. document_reviewer'), 'broken_policy');
    await user.selectOptions(screen.getByLabelText('Resource type', { selector: 'select' }), 'policies');
    await user.click(screen.getByRole('tab', { name: /^Actions/ }));
    await user.click(await screen.findByText('Read/list policies.'));
    await user.click(screen.getByRole('button', { name: 'Create policy' }));

    expect(await screen.findByText('Failed to create policy')).toBeInTheDocument();
  });

  it('opens the edit form pre-filled and submits an update via PUT', async () => {
    seed(['policies:read', 'policies:update']);
    mock.onGet('/authorization/policies').reply(200, SAMPLE_POLICIES);
    mock.onGet('/authorization/permissions/catalog').reply(200, PERMISSION_CATALOG);
    mock.onPut('/authorization/policies/report_viewer').reply(200, {
      ...SAMPLE_POLICIES[0],
      description: 'Updated description',
    });

    renderPage();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    expect(screen.getByDisplayValue('report_viewer')).toBeInTheDocument();

    const descriptionInput = screen.getByDisplayValue('Basic report viewing access');
    await user.clear(descriptionInput);
    await user.type(descriptionInput, 'Updated description');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toMatchObject({ description: 'Updated description' });
  });
});
