import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';

import { useLanguageStore } from '@/store/languageStore';
import LanguageToggle from '@/layout/LanguageToggle';

const initialLanguageState = useLanguageStore.getState();

function renderToggle() {
  return render(
    <ChakraProvider value={defaultSystem}>
      <LanguageToggle />
    </ChakraProvider>
  );
}

describe('LanguageToggle', () => {
  beforeEach(() => {
    useLanguageStore.setState(initialLanguageState, true);
    useLanguageStore.getState().setMode('en');
  });

  it('shows the current mode\'s label at rest, without needing to open the dropdown', () => {
    useLanguageStore.getState().setMode('en+hi');
    renderToggle();

    expect(screen.getByRole('combobox')).toHaveTextContent('English + हिंदी');
  });

  it('shows all five language modes when opened', async () => {
    renderToggle();

    await userEvent.click(screen.getByRole('combobox'));

    expect(screen.getByRole('option', { name: 'English' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'हिंदी (Hindi)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'मराठी (Marathi)' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'English + हिंदी' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'English + मराठी' })).toBeInTheDocument();
  });

  it('selecting the "English + मराठी" option sets the mixed en+mr mode in the store, with chrome staying English', async () => {
    renderToggle();

    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(screen.getByRole('option', { name: 'English + मराठी' }));

    expect(useLanguageStore.getState().mode).toBe('en+mr');
    expect(useLanguageStore.getState().chromeLanguage).toBe('en');
    expect(useLanguageStore.getState().pageLanguage).toBe('mr');
  });

  it('selecting a plain "हिंदी (Hindi)" option sets both chrome and page to hi', async () => {
    renderToggle();

    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(screen.getByRole('option', { name: 'हिंदी (Hindi)' }));

    expect(useLanguageStore.getState().mode).toBe('hi');
    expect(useLanguageStore.getState().chromeLanguage).toBe('hi');
    expect(useLanguageStore.getState().pageLanguage).toBe('hi');
  });

  it('re-selecting a different option after one is already chosen works in a single click, no clearing needed', async () => {
    renderToggle();

    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(screen.getByRole('option', { name: 'हिंदी (Hindi)' }));
    expect(useLanguageStore.getState().mode).toBe('hi');

    await userEvent.click(screen.getByRole('combobox'));
    await userEvent.click(screen.getByRole('option', { name: 'English + मराठी' }));

    expect(useLanguageStore.getState().mode).toBe('en+mr');
  });
});
