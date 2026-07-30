import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dirname = path.dirname(fileURLToPath(import.meta.url));

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
  ],
  resolve: {
    // Mirrors tsconfig.app.json's "paths" and vitest.config.ts's identical
    // alias — those only affect TypeScript's type-checker and Vitest
    // respectively, not Vite's own dev-server/build module resolution,
    // which needs this explicitly. Without it, `vite`/`vite dev` fails to
    // resolve every `@/...`/`@app/...` import at request time ("Failed to
    // resolve import... Does the file exist?") even though `vite build`
    // (Rollup) happens to still succeed — a real, deterministic dev-server
    // break, not a flaky one.
    alias: {
      '@': path.resolve(dirname, 'src/mystic_auth'),
      '@app': path.resolve(dirname, 'src/app'),
    },
  },
  // No custom build.rollupOptions.output.manualChunks here — a prior
  // version forced every node_modules import into one "vendor" chunk for
  // better long-term caching (rarely-changing third-party code under a
  // stable hash, separate from app code that changes every deploy). That
  // broke production: app/src files like api/axiosInstance.ts both import
  // from and get imported by that vendor chunk, and Rollup placed shared
  // CJS-interop helpers into axiosInstance's own chunk — creating a real
  // circular chunk dependency. ESM's live-binding semantics for circular
  // imports meant vendor.js called a binding from axiosInstance.js's chunk
  // before that chunk's module body had run far enough to define it,
  // throwing "TypeError: t is not a function" at the very top of the
  // vendor bundle — the whole app failed to mount, a blank page with no
  // build-time warning. Reverting to Rollup's own automatic chunking
  // (its default module-graph analysis doesn't create this circular
  // dependency) trades away that caching optimization for a build that
  // actually works; re-introduce chunking later only with real production
  // verification (not just curl on the built files) that nothing crashes.
});
