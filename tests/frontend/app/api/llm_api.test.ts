import { describe, it, expect, beforeEach } from 'vitest';
import MockAdapter from 'axios-mock-adapter';
import api from '@/api/axiosInstance';
import { chatApi } from '@app/api/llm_api';

const mock = new MockAdapter(api);

beforeEach(() => {
  mock.reset();
});

describe('chatApi', () => {
  it('sends a POST request with company_id and question, returns the grounded answer', async () => {
    const payload = { company_id: 5, question: 'How are total assets trending?' };
    mock.onPost('/llm/chat', payload).reply(200, { answer: 'Total assets grew year over year.' });

    const response = await chatApi(payload);

    expect(response.status).toBe(200);
    expect(response.data).toEqual({ answer: 'Total assets grew year over year.' });
  });

  it("propagates a 403 for a company outside the caller's scope", async () => {
    const payload = { company_id: 99, question: 'Anything?' };
    mock.onPost('/llm/chat', payload).reply(403, { detail: 'Insufficient permissions' });

    await expect(chatApi(payload)).rejects.toMatchObject({ response: { status: 403 } });
  });

  it('propagates a 502 when the LLM provider fails', async () => {
    const payload = { company_id: 5, question: 'Anything?' };
    mock.onPost('/llm/chat', payload).reply(502, { detail: 'Groq API error (500): boom' });

    await expect(chatApi(payload)).rejects.toMatchObject({ response: { status: 502 } });
  });

  it('supports an optional years filter', async () => {
    const payload = { company_id: 5, question: 'Compare 2022 and 2023', years: [2022, 2023] };
    mock.onPost('/llm/chat', payload).reply(200, { answer: 'Comparison here.' });

    const response = await chatApi(payload);

    expect(response.status).toBe(200);
  });
});
