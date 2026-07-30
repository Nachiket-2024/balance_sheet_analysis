import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { listCompaniesApi, getCompanyApi, createCompanyApi } from '@app/api/company_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('listCompaniesApi', () => {
  it('sends a GET request to /companies/', async () => {
    mock.onGet('/companies/').reply(200, []);

    const response = await listCompaniesApi();

    expect(response.status).toBe(200);
    expect(response.data).toEqual([]);
  });

  it('propagates a 403 (the caller is unauthenticated/unauthorized for this action)', async () => {
    mock.onGet('/companies/').reply(403, { detail: 'Forbidden' });

    await expect(listCompaniesApi()).rejects.toMatchObject({ response: { status: 403 } });
  });
});

describe('getCompanyApi', () => {
  it('sends a GET request to /companies/{id}', async () => {
    mock.onGet('/companies/42').reply(200, { id: 42, name: 'Jio Platforms' });

    const response = await getCompanyApi(42);

    expect(response.data).toMatchObject({ id: 42 });
  });

  it("propagates a 403 for a company outside the caller's scope", async () => {
    mock.onGet('/companies/99').reply(403, { detail: 'Insufficient permissions' });

    await expect(getCompanyApi(99)).rejects.toMatchObject({ response: { status: 403 } });
  });
});

describe('createCompanyApi', () => {
  it('sends a POST request with the new company payload', async () => {
    const payload = { name: 'Jio Platforms', ticker: 'JIO.NS', parent_company_id: 1 };
    mock.onPost('/companies/', payload).reply(201, { id: 2, ...payload });

    const response = await createCompanyApi(payload);

    expect(response.status).toBe(201);
    expect(response.data).toMatchObject(payload);
  });
});
