import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { ChakraProvider } from '@chakra-ui/react';

import App from './App.tsx';
import ErrorBoundary from '../mystic_auth/ui/ErrorBoundary.tsx';

// The app's custom Chakra system (theme tokens/semantic tokens), built on
// top of Chakra's defaultConfig rather than replacing it.
import { system } from '../mystic_auth/theme/system.ts';

// Auth/permissions state itself lives in Zustand (store/authStore.ts),
// which needs no Provider since it's a module-level singleton reachable
// from any component directly.
import { queryClient } from "../mystic_auth/core/queryClient.ts";

// Imported here, eagerly, purely for its module-load side effect of
// applying the persisted/OS color mode class to <html> BEFORE the first
// paint. Importing it later (e.g. only from Navbar, where the toggle
// button lives) would apply that class after React's first render,
// causing a visible flash of the wrong theme for a user who previously
// chose dark mode.
import '../mystic_auth/store/themeStore.ts';

// Must be called once, before the app renders, so every API call made
// during the initial session check is already covered.
import { setupAuthInterceptor } from "../mystic_auth/auth/session_lifecycle/setupAuthInterceptor.ts";

// A no-op unless VITE_SENTRY_DSN is set. See core/errorMonitoring.ts and
// docs/mystic_auth/error-monitoring/overview.md. Called before render so a crash during the
// app's very first render is still reportable.
import { initErrorMonitoring } from "../mystic_auth/core/errorMonitoring.ts";

const rootElement = document.getElementById('root') as HTMLElement;

setupAuthInterceptor();
initErrorMonitoring();

ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
        <ErrorBoundary>
            <QueryClientProvider client={queryClient}>
                <ChakraProvider value={system}>
                    <App />
                </ChakraProvider>
            </QueryClientProvider>
        </ErrorBoundary>
    </React.StrictMode>
);
