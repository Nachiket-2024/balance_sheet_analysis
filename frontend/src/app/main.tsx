import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';

import App from './App.tsx';
import ErrorBoundary from '../mystic_auth/ui/routing/ErrorBoundary.tsx';

// Self-hosted, not a Google Fonts CDN request (consistent with this
// template's other self-hosted defaults). Registers "InterVariable" before
// first paint, which tailwind.css's font-sans stack references.
// CSS-only import, no JS export: kept only for that load side effect.
import '@fontsource-variable/inter';

// The production build marks the stylesheet as media="print" so it can be
// fetched without blocking the first HTML paint. Looked up once here and
// reused below (querying by [media="print"] again after removeAttribute
// would never match, since the attribute is already gone by then).
const stylesheet = document.querySelector<HTMLLinkElement>('link[rel="stylesheet"][media="print"]');
stylesheet?.removeAttribute("media");

// Tailwind v4 entry point + design tokens (see theme/tailwind.css).
// applyBrandCssVars.ts applies the signed-in user's brand-color pick as
// CSS variables: eager, side-effect-only import, same "before first
// paint" pattern as themeStore.ts below.
import '../mystic_auth/theme/tailwind.css';
import '../mystic_auth/theme/applyBrandCssVars.ts';

// Auth/permissions state lives in Zustand (store/authStore.ts), which needs
// no Provider since it's a module-level singleton reachable directly.
import { queryClient } from "../mystic_auth/core/queryClient.ts";

// Eager, side-effect-only import: applies the persisted/OS color mode class
// to <html> before first paint. Importing it later (e.g. only from Navbar)
// would flash the wrong theme for a user who previously chose dark mode.
import '../mystic_auth/store/themeStore.ts';

// Same reasoning as themeStore.ts, for the persisted custom brand/background
// colors: applies the favicon/meta tag before first paint (the --brand-*
// CSS vars themselves come from applyBrandCssVars.ts above, reading this
// module's cached state). This is just the locally cached guess;
// useAuthSession reconciles it against the server value once GET /auth/me
// resolves.
import '../mystic_auth/store/appearanceStore.ts';

// Same reasoning as themeStore.ts, for the persisted font-size preference:
// applies before first paint, avoiding a flash of the wrong size.
import '../mystic_auth/store/fontSizeStore.ts';

// Same reasoning as themeStore.ts, for the persisted/browser language
// preference: also eagerly initializes translations/translations.ts, so
// this import both configures translations and applies the chosen
// language before first paint.
import '../mystic_auth/store/languageStore.ts';
import { prefetchRoute } from '../mystic_auth/layout/app_layout/routePrefetch';

// This app's own translation resources (companies/balance_sheets/analysis/llm
// namespaces, plus this app's own error codes). Imported after
// languageStore.ts above so mystic_auth's i18next instance is already
// initialized by the time this registers into it - see
// translations/translations.ts's own comment for why this is a registration
// into the shared instance, not a second one.
import './translations/translations.ts';

// Must be called once, before the app renders, so every API call made
// during the initial session check is already covered.
import { setupAuthInterceptor } from "../mystic_auth/auth/session_lifecycle/setupAuthInterceptor.ts";

// A no-op unless VITE_SENTRY_DSN is set. See core/errorMonitoring.ts and
// docs/mystic_auth/error-monitoring/overview.md. Called before render so a crash during the
// app's very first render is still reportable.
import { initErrorMonitoring } from "../mystic_auth/core/errorMonitoring.ts";

const rootElement = document.getElementById('root') as HTMLElement;

// Start the protected route chunk while the app shell and session request are
// starting. The same dynamic import is reused by React.lazy, so this removes
// the route fetch from the critical render sequence without making every route
// part of the initial bundle.
prefetchRoute(window.location.pathname);

function mountApp(): void {
    setupAuthInterceptor();
    initErrorMonitoring();

    ReactDOM.createRoot(rootElement).render(
                <React.StrictMode>
                    <ErrorBoundary>
                        <QueryClientProvider client={queryClient}>
                            <App />
                        </QueryClientProvider>
                    </ErrorBoundary>
                </React.StrictMode>
    );
}

const stylesheetIsReady = stylesheet?.sheet && (() => {
    try {
        return stylesheet.sheet.cssRules.length > 0;
    } catch {
        return false;
    }
})();
if (stylesheet && !stylesheetIsReady) {
    stylesheet.addEventListener("load", mountApp, { once: true });
} else {
    mountApp();
}
