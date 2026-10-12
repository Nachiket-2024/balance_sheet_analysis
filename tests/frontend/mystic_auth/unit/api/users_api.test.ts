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
  exportUsersApi,
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

describe('exportUsersApi', () => {
  it('sends a GET request to /users/export with responseType blob and passes filters through', async () => {
    const csvBlob = new Blob(['id,name,email\n'], { type: 'text/csv' });
    mock.onGet('/users/export').reply((config) => {
      expect(config.responseType).toBe('blob');
      expect(config.params).toMatchObject({ role: 'admin', status: 'active' });
      return [200, csvBlob, { 'content-disposition': 'attachment; filename="users_export_20260101T000000Z.csv"' }];
    });

    const response = await exportUsersApi({ role: 'admin', status: 'active' });

    expect(response.status).toBe(200);
    expect(response.headers['content-disposition']).toContain('users_export_');
  });

  it('propagates a 403 when the caller lacks users:list_all', async () => {
    mock.onGet('/users/export').reply(403, { detail: 'Forbidden' });

    await expect(exportUsersApi()).rejects.toMatchObject({ response: { status: 403 } });
  });
});

describe('listUsersApi with policy/permission filters', () => {
  it('passes policy and permission through as query params', async () => {
    mock.onGet('/users/').reply((config) => {
      expect(config.params).toMatchObject({ policy: 'user_management', permission: 'users:list_all' });
      return [200, []];
    });

    const response = await listUsersApi({ policy: 'user_management', permission: 'users:list_all' });

    expect(response.status).toBe(200);
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
