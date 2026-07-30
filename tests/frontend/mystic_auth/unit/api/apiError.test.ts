import { describe, it, expect } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import { extractApiErrorMessage } from '@/api/apiError';

function makeAxiosError(data: unknown): AxiosError {
  return new AxiosError('Request failed', undefined, undefined, undefined, {
    data,
    status: 400,
    statusText: 'Bad Request',
    headers: {},
    config: { headers: new AxiosHeaders() },
  });
}

describe('extractApiErrorMessage', () => {
  it('reads this app\'s own { error: string } shape', () => {
    expect(extractApiErrorMessage(makeAxiosError({ error: 'Invalid credentials or account locked' }), 'fallback'))
      .toBe('Invalid credentials or account locked');
  });

  it('reads FastAPI\'s native { detail: string } shape (HTTPException)', () => {
    expect(extractApiErrorMessage(makeAxiosError({ detail: 'Password does not meet minimum strength requirements' }), 'fallback'))
      .toBe('Password does not meet minimum strength requirements');
  });

  it('prefers { error } over { detail } when both are present', () => {
    expect(extractApiErrorMessage(makeAxiosError({ error: 'from error', detail: 'from detail' }), 'fallback'))
      .toBe('from error');
  });

  it('falls back when detail is a list of Pydantic validation errors, not a string', () => {
    expect(
      extractApiErrorMessage(
        makeAxiosError({ detail: [{ type: 'value_error', loc: ['body', 'email'], msg: 'bad email' }] }),
        'fallback'
      )
    ).toBe('fallback');
  });

  it('falls back for a non-axios error', () => {
    expect(extractApiErrorMessage(new Error('network down'), 'fallback')).toBe('fallback');
  });

  it('falls back when the response body has neither error nor detail', () => {
    expect(extractApiErrorMessage(makeAxiosError({ message: 'something else' }), 'fallback')).toBe('fallback');
  });
});
