import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import {
  listCompanyBalanceSheetsApi,
  getCompanyBalanceSheetApi,
  importCompanyBalanceSheetApi,
  deleteCompanyBalanceSheetApi,
} from '@app/api/balance_sheet_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('listCompanyBalanceSheetsApi', () => {
  it('sends a GET request to /balance-sheets/company/{companyId}', async () => {
    mock.onGet('/balance-sheets/company/5').reply(200, [{ id: 1, company_id: 5, year: 2023 }]);

    const response = await listCompanyBalanceSheetsApi(5);

    expect(response.data).toHaveLength(1);
    expect(response.data[0]).toMatchObject({ company_id: 5, year: 2023 });
  });
});

describe('getCompanyBalanceSheetApi', () => {
  it('sends a GET request to /balance-sheets/{companyId}/{year}', async () => {
    mock.onGet('/balance-sheets/5/2023').reply(200, { id: 1, company_id: 5, year: 2023 });

    const response = await getCompanyBalanceSheetApi(5, 2023);

    expect(response.data.year).toBe(2023);
  });

  it('propagates a 404 when no balance sheet exists for that year', async () => {
    mock.onGet('/balance-sheets/5/1999').reply(404, { detail: 'Balance sheet not found' });

    await expect(getCompanyBalanceSheetApi(5, 1999)).rejects.toMatchObject({ response: { status: 404 } });
  });
});

describe('importCompanyBalanceSheetApi', () => {
  it('sends a POST request to import a fiscal year from yfinance', async () => {
    mock.onPost('/balance-sheets/5/2024').reply(201, { id: 2, company_id: 5, year: 2024 });

    const response = await importCompanyBalanceSheetApi(5, 2024);

    expect(response.status).toBe(201);
  });
});

describe('deleteCompanyBalanceSheetApi', () => {
  it('sends a DELETE request for the given company/year', async () => {
    mock.onDelete('/balance-sheets/5/2024').reply(204);

    const response = await deleteCompanyBalanceSheetApi(5, 2024);

    expect(response.status).toBe(204);
  });
});
