import { defineConfig, type Plugin } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dirname = path.dirname(fileURLToPath(import.meta.url));

// Test files live at ../tests/frontend — outside this project's root, per
// the repository's top-level tests/backend + tests/frontend layout. Node's
// (and Vite's) module resolution for bare specifiers walks *up* from the
// importing file's own directory looking for a node_modules folder; since
// tests/frontend is a sibling of frontend/, not a descendant, that walk
// never reaches frontend/node_modules and bare imports (axios-mock-adapter,
// @testing-library/*, etc.) fail to resolve. The dependencies must stay
// owned by the frontend project (no root node_modules, no duplicated
// installs) — see the resolveExternalTestImports plugin below, which
// fixes resolution instead of relocating dependencies.
const externalTestsDir = path.resolve(dirname, '../tests/frontend').replace(/\\/g, '/');

/**
 * Vite plugin: for source files outside this project root (i.e. under
 * tests/frontend), re-resolve their bare-specifier imports as if they were
 * imported from inside frontend/src instead. Uses Vite's own resolver
 * (`this.resolve`) rather than a raw `require.resolve` fallback, so
 * resolution behaves identically to a normal in-project import (respects
 * package.json "exports"/"browser" fields, conditions, etc.) — the only
 * difference is which directory the upward node_modules search starts
 * from. Imports from files inside frontend/ are left untouched; they
 * already resolve correctly through Vite's default pipeline.
 */
function resolveExternalTestImports(): Plugin {
  const fakeInternalImporter = path.join(
    dirname,
    'src',
    '__external_test_import__.ts',
  );

  return {
    name: 'resolve-external-test-imports',
    enforce: 'pre',

    async resolveId(
      source: string,
      importer: string | undefined,
    ): Promise<string | null> {
      if (!importer) return null;

      if (
        source.startsWith('.') ||
        source.startsWith('/') ||
        path.isAbsolute(source)
      ) {
        return null;
      }

      const normalizedImporter = importer.replace(/\\/g, '/');

      if (!normalizedImporter.startsWith(externalTestsDir)) {
        return null;
      }

      const resolved = await this.resolve(source, fakeInternalImporter, {
        skipSelf: true,
      });

      return resolved?.id ?? null;
    },
  };
}

export default defineConfig({
  plugins: [react(), resolveExternalTestImports()],

  resolve: {
    alias: {
      // Lets test files (and app source) import frontend/src/mystic_auth
      // modules with a stable, depth-independent path instead of brittle
      // relative chains like "../../../../../frontend/src/mystic_auth/api/auth_api".
      '@': path.resolve(dirname, 'src/mystic_auth'),
      // Separate alias for the thin app shell (App.tsx/main.tsx/sdk.ts/
      // app_sdk.ts) living outside mystic_auth/ — only needed by the rare
      // test that exercises the app root directly (e.g. app_routing.test.tsx).
      '@app': path.resolve(dirname, 'src/app'),
    },
  },

  server: {
    // Vite's dev server restricts filesystem access to the project root by
    // default — without this, the test runner can't even read files under
    // ../tests.
    fs: {
      allow: ['..'],
    },
  },

  test: {
    globals: true,
    environment: 'jsdom',

    include: [
      '../tests/frontend/**/*.test.{ts,tsx}',
    ],

    setupFiles: [
      './src/mystic_auth/__tests__/setup.ts',
    ],

    coverage: {
      provider: 'v8',
      reporter: [
        'text',
        'json',
        'html',
      ],
      // Current coverage is ~89%/82%/84%/90% (statements/branches/functions/
      // lines — see docs/mystic_auth/testing/overview.md); thresholds sit a few points
      // below that as a regression alarm, not a strict target, so
      // incidental coverage drift doesn't flap CI red. Only enforced when
      // coverage is actually collected (`vitest run --coverage`, i.e. the
      // `test:coverage` script CI runs) — plain `test` never evaluates
      // these.
      thresholds: {
        statements: 85,
        branches: 78,
        functions: 79,
        lines: 86,
      },
    },
  },
});