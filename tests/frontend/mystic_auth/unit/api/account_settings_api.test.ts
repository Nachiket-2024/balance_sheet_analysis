import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { confirmDeleteMyAccountApi, deleteMyAccountApi, updateMyAccountApi } from '@/api/account_settings_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('updateMyAccountApi', () => {
  it('sends a PUT request to /users/me with the payload', async () => {
    const payload = { name: 'New Name' };
    const mockResponse = { id: 1, name: 'New Name', email: 'a@example.com' };
    mock.onPut('/users/me', payload).reply(200, mockResponse);

    const response = await updateMyAccountApi(payload);

    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });
});

describe('deleteMyAccountApi', () => {
  it('sends a DELETE request to /users/me with the payload as the request body', async () => {
    const payload = { current_password: 'StrongPass123!' };
    const mockResponse = { detail: 'Your account has been deleted' };
    mock.onDelete('/users/me', { data: payload }).reply(200, mockResponse);

    const response = await deleteMyAccountApi(payload);

    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });

  it('returns confirmation_required for an OAuth-only account instead of deleting immediately', async () => {
    const mockResponse = { detail: 'Check your email to confirm deleting your account', confirmation_required: true };
    mock.onDelete('/users/me').reply(200, mockResponse);

    const response = await deleteMyAccountApi({});

    expect(response.data.confirmation_required).toBe(true);
  });
});

describe('confirmDeleteMyAccountApi', () => {
  it('sends a POST request to /users/me/confirm-delete with the token', async () => {
    const payload = { token: 'delete-token-abc' };
    const mockResponse = { message: 'Your account has been deleted' };
    mock.onPost('/users/me/confirm-delete', payload).reply(200, mockResponse);

    const response = await confirmDeleteMyAccountApi(payload);

    expect(response.status).toBe(200);
    expect(response.data).toEqual(mockResponse);
  });
});
