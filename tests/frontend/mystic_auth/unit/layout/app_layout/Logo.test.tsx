import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

async function renderLogo() {
  const { default: Logo } = await import('@/layout/app_layout/Logo');
  return render(
      <Logo />
  );
}

describe('Logo', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('renders the built-in icon + wordmark when no logo URL is configured', async () => {
    vi.stubEnv('VITE_APP_LOGO_URL', '');

    await renderLogo();

    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByText((await import('@/core/settings')).APP_NAME)).toBeInTheDocument();
  });

  it('renders an <img> instead of the built-in mark when VITE_APP_LOGO_URL is set', async () => {
    vi.stubEnv('VITE_APP_LOGO_URL', 'https://example.com/logo.png');

    await renderLogo();

    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', 'https://example.com/logo.png');
  });
});
