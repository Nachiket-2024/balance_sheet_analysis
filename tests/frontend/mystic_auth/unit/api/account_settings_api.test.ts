import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { updateMyAccountApi } from '@/api/account_settings_api';

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
