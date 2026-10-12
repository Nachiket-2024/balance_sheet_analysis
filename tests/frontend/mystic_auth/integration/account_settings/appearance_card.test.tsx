import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';

import api from '@/api/axiosInstance';
import AppearanceCard from '@/account_settings/AppearanceCard';
import { useAppearanceStore } from '@/store/appearanceStore';

const mock = new MockAdapter(api);
const initialAppearanceState = useAppearanceStore.getState();

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
        <AppearanceCard />
    </QueryClientProvider>
  );
}

// AppearanceCard debounces the store commit by 100ms (COMMIT_DEBOUNCE_MS).
// Wait past that window instead of using fake timers, since userEvent.type
// runs on real timers.
const PAST_DEBOUNCE = { timeout: 1000 };

describe('AppearanceCard', () => {
  beforeEach(() => {
    mock.reset();
    window.localStorage.clear();
    useAppearanceStore.setState(initialAppearanceState, true);
    mock.onPut('/users/me').reply(200, { brand_color: '#2563eb' });
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('defaults the hex field to the shipped terracotta brand when nothing is customized', () => {
    renderCard();

    expect(screen.getByRole('textbox')).toHaveValue('#b5533c');
  });

  it('preloads the hex field from an already-customized brand color', () => {
    useAppearanceStore.getState().setBrandColor('#16a34a');

    renderCard();

    expect(screen.getByRole('textbox')).toHaveValue('#16a34a');
  });

  it('shows a validation error and disables Save for an invalid hex value', async () => {
    renderCard();
    const user = userEvent.setup();

    const hexField = screen.getByRole('textbox');
    await user.clear(hexField);
    await user.type(hexField, 'not-a-color');

    expect(await screen.findByText(/enter a valid hex color/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  });

  it('commits a valid pick to appearanceStore after the debounce window, without waiting for Save', async () => {
    renderCard();
    const user = userEvent.setup();

    const hexField = screen.getByRole('textbox');
    await user.clear(hexField);
    await user.type(hexField, '#16a34a');

    await waitFor(
      () => expect(useAppearanceStore.getState().brandColor).toBe('#16a34a'),
      PAST_DEBOUNCE
    );
  });

  it('renders live light/dark preview swatches once the hex is valid', async () => {
    renderCard();
    const user = userEvent.setup();

    const hexField = screen.getByRole('textbox');
    await user.clear(hexField);
    await user.type(hexField, '#16a34a');

    expect(await screen.findByText('Light mode preview')).toBeInTheDocument();
    expect(screen.getByText('Dark mode preview')).toBeInTheDocument();
  });

  it('Save persists the picked color via PUT /users/me and shows a success toast', async () => {
    renderCard();
    const user = userEvent.setup();

    const hexField = screen.getByRole('textbox');
    await user.clear(hexField);
    await user.type(hexField, '#2563eb');

    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ brand_color: '#2563eb' });
    await waitFor(() => expect(useAppearanceStore.getState().brandColor).toBe('#2563eb'));
  });

  it('Reset clears back to the default color and persists brand_color: null', async () => {
    useAppearanceStore.getState().setBrandColor('#16a34a');
    mock.onPut('/users/me').reply(200, { brand_color: null });

    renderCard();
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'Reset to default' }));

    await waitFor(() => expect(mock.history.put.length).toBe(1));
    expect(JSON.parse(mock.history.put[0].data)).toEqual({ brand_color: null });
    expect(useAppearanceStore.getState().brandColor).toBeNull();
    expect(screen.getByRole('textbox')).toHaveValue('#b5533c');
  });

  it('shows an error alert when the save request fails', async () => {
    mock.onPut('/users/me').reply(500);

    renderCard();
    const user = userEvent.setup();

    const hexField = screen.getByRole('textbox');
    await user.clear(hexField);
    await user.type(hexField, '#2563eb');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText(/failed to update profile/i)).toBeInTheDocument();
  });
});
