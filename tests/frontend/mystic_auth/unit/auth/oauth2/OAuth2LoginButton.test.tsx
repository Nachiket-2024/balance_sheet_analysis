// Regression: OAuth2LoginButton used to hardcode error={null}, so a failed
// login (e.g. a soft-deleted account) redirected to /login?error=<code> with
// no explanation. These tests confirm the param is read, translated,
// displayed, and stripped from the URL.
import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';

import OAuth2LoginButton from '@/auth/oauth2/OAuth2LoginButton';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

function renderAt(path: string) {
  return render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/login"
            element={
              <>
                <OAuth2LoginButton />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
  );
}

describe('OAuth2LoginButton', () => {
  it('translates a known ?error= code from the OAuth2 redirect and displays it', async () => {
    renderAt('/login?error=ACCOUNT_DELETED');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('This account has been deleted');
    });
  });

  it('strips the error param from the URL after reading it', async () => {
    renderAt('/login?error=ACCOUNT_DEACTIVATED');

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByTestId('location-search')).toHaveTextContent('');
  });

  it('renders no alert when there is no error param', () => {
    renderAt('/login');

    expect(screen.queryByRole('alert')).toBeNull();
  });
});
