import { describe, it, expect, vi, beforeEach } from 'vitest';

const sentryInit = vi.fn();
const sentryCaptureException = vi.fn();

vi.mock('@sentry/react', () => ({
  init: sentryInit,
  captureException: sentryCaptureException,
}));

describe('errorMonitoring', () => {
  beforeEach(() => {
    vi.resetModules();
    sentryInit.mockClear();
    sentryCaptureException.mockClear();
    vi.unstubAllEnvs();
  });

  describe('initErrorMonitoring', () => {
    it('does not initialize the SDK when VITE_SENTRY_DSN is unset', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');
      const { initErrorMonitoring } = await import('@/core/errorMonitoring');

      initErrorMonitoring();

      // .not.toHaveBeenCalled() doesn't type-check here : see
      // docs/mystic_auth/testing/overview.md's ".not chaining" note.
      expect(sentryInit).toHaveBeenCalledTimes(0);
    });

    it('initializes the SDK with the configured DSN when set', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://examplePublicKey@o0.ingest.example.com/0');
      vi.stubEnv('VITE_SENTRY_ENVIRONMENT', 'staging');
      const { initErrorMonitoring } = await import('@/core/errorMonitoring');

      initErrorMonitoring();

      expect(sentryInit).toHaveBeenCalledOnce();
      const [options] = sentryInit.mock.calls[0];
      expect(options.dsn).toBe('https://examplePublicKey@o0.ingest.example.com/0');
      expect(options.environment).toBe('staging');
    });
  });

  describe('reportError', () => {
    it('does not call the SDK when VITE_SENTRY_DSN is unset', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', '');
      const { reportError } = await import('@/core/errorMonitoring');

      reportError(new Error('boom'));

      expect(sentryCaptureException).toHaveBeenCalledTimes(0);
    });

    it('reports the error via the SDK when a DSN is configured', async () => {
      vi.stubEnv('VITE_SENTRY_DSN', 'https://examplePublicKey@o0.ingest.example.com/0');
      const { reportError } = await import('@/core/errorMonitoring');
      const error = new Error('boom');

      reportError(error, { componentStack: 'at Bomb' });

      expect(sentryCaptureException).toHaveBeenCalledWith(error, { extra: { componentStack: 'at Bomb' } });
    });
  });
});
