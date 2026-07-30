import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import {
  listPoliciesApi,
  getPolicyApi,
  createPolicyApi,
  updatePolicyApi,
  deletePolicyApi,
  getPolicyHistoryApi,
  assignPolicyApi,
  revokePolicyApi,
  getMyPoliciesApi,
  getUserPoliciesApi,
} from '@/api/policies_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('listPoliciesApi', () => {
  it('sends a GET request to /authorization/policies', async () => {
    mock.onGet('/authorization/policies').reply(200, []);

    const response = await listPoliciesApi();

    expect(response.status).toBe(200);
  });
});

describe('getPolicyApi', () => {
  it('URL-encodes the policy name in the path', async () => {
    const name = 'policy with spaces';
    mock.onGet(`/authorization/policies/${encodeURIComponent(name)}`).reply(200, { name });

    const response = await getPolicyApi(name);

    expect(response.data).toEqual({ name });
  });
});

describe('createPolicyApi', () => {
  it('sends a POST request with the policy payload', async () => {
    const payload = { name: 'p1', actions: ['users:read_own'], resource_type: 'users' };
    mock.onPost('/authorization/policies', payload).reply(201, { id: 1, ...payload });

    const response = await createPolicyApi(payload);

    expect(response.status).toBe(201);
  });
});

describe('updatePolicyApi', () => {
  it('sends a PUT request to the encoded policy path with the update payload', async () => {
    const payload = { description: 'updated' };
    mock.onPut(`/authorization/policies/${encodeURIComponent('p1')}`, payload).reply(200, {});

    const response = await updatePolicyApi('p1', payload);

    expect(response.status).toBe(200);
  });
});

describe('deletePolicyApi', () => {
  it('sends a DELETE request with an optional reason query param', async () => {
    mock.onDelete(`/authorization/policies/${encodeURIComponent('p1')}`).reply((config) => {
      expect(config.params).toEqual({ reason: 'no longer needed' });
      return [204];
    });

    const response = await deletePolicyApi('p1', 'no longer needed');

    expect(response.status).toBe(204);
  });
});

describe('getPolicyHistoryApi', () => {
  it('defaults limit/offset when not provided', async () => {
    mock.onGet(`/authorization/policies/${encodeURIComponent('p1')}/history`).reply((config) => {
      expect(config.params).toEqual({ limit: 50, offset: 0 });
      return [200, []];
    });

    await getPolicyHistoryApi('p1');
  });

  it('passes explicit limit/offset through', async () => {
    mock.onGet(`/authorization/policies/${encodeURIComponent('p1')}/history`).reply((config) => {
      expect(config.params).toEqual({ limit: 10, offset: 20 });
      return [200, []];
    });

    await getPolicyHistoryApi('p1', 10, 20);
  });
});

describe('assignPolicyApi', () => {
  it('sends a POST request with the policy_name in the body', async () => {
    const email = 'user@example.com';
    mock
      .onPost(`/authorization/users/${encodeURIComponent(email)}/policies`, { policy_name: 'p1' })
      .reply(201, {});

    const response = await assignPolicyApi(email, 'p1');

    expect(response.status).toBe(201);
  });
});

describe('revokePolicyApi', () => {
  it('sends a DELETE request to the encoded user+policy path', async () => {
    const email = 'user@example.com';
    mock
      .onDelete(`/authorization/users/${encodeURIComponent(email)}/policies/${encodeURIComponent('p1')}`)
      .reply(204);

    const response = await revokePolicyApi(email, 'p1');

    expect(response.status).toBe(204);
  });
});

describe('getMyPoliciesApi', () => {
  it('sends a GET request to /authorization/users/me/policies', async () => {
    mock.onGet('/authorization/users/me/policies').reply(200, { user_email: 'me@example.com', policies: [] });

    const response = await getMyPoliciesApi();

    expect(response.data.user_email).toBe('me@example.com');
  });
});

describe('getUserPoliciesApi', () => {
  it('URL-encodes the target user email in the path', async () => {
    const email = 'user+tag@example.com';
    mock
      .onGet(`/authorization/users/${encodeURIComponent(email)}/policies`)
      .reply(200, { user_email: email, policies: [] });

    const response = await getUserPoliciesApi(email);

    expect(response.data.user_email).toBe(email);
  });
});
