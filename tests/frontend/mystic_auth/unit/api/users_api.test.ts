import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import {
  listUsersApi,
  updateUserApi,
  deleteUserApi,
  purgeUserApi,
  reactivateUserApi,
  updateUserRoleApi,
} from '@/api/users_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('listUsersApi', () => {
  it('sends a GET request to /users/', async () => {
    mock.onGet('/users/').reply(200, []);

    const response = await listUsersApi();

    expect(response.status).toBe(200);
    expect(response.data).toEqual([]);
  });

  it('propagates a 403 when the caller lacks users:list_all', async () => {
    mock.onGet('/users/').reply(403, { detail: 'Forbidden' });

    await expect(listUsersApi()).rejects.toMatchObject({ response: { status: 403 } });
  });
});

describe('updateUserApi', () => {
  it('URL-encodes the target email in the path', async () => {
    const email = 'user+admin@example.com';
    mock.onPut(`/users/${encodeURIComponent(email)}`).reply(200, {});

    const response = await updateUserApi(email, { name: 'Renamed' });

    expect(response.status).toBe(200);
  });
});

describe('deleteUserApi', () => {
  it('sends a DELETE request to the encoded user path (soft delete)', async () => {
    const email = 'user@example.com';
    mock.onDelete(`/users/${encodeURIComponent(email)}`).reply(204);

    const response = await deleteUserApi(email);

    expect(response.status).toBe(204);
  });
});

describe('purgeUserApi', () => {
  it('sends a DELETE request to the /purge subpath (hard delete)', async () => {
    const email = 'user@example.com';
    mock.onDelete(`/users/${encodeURIComponent(email)}/purge`).reply(204);

    const response = await purgeUserApi(email);

    expect(response.status).toBe(204);
  });
});

describe('reactivateUserApi', () => {
  it('sends a PATCH request to the /reactivate subpath', async () => {
    const email = 'user@example.com';
    mock.onPatch(`/users/${encodeURIComponent(email)}/reactivate`).reply(200, { is_active: true });

    const response = await reactivateUserApi(email);

    expect(response.data).toEqual({ is_active: true });
  });
});

describe('updateUserRoleApi', () => {
  it('sends a PATCH request to the /role subpath with the new role', async () => {
    const email = 'user@example.com';
    mock.onPatch(`/users/${encodeURIComponent(email)}/role`, { role: 'admin' }).reply(200, {});

    const response = await updateUserRoleApi(email, 'admin');

    expect(response.status).toBe(200);
  });
});
