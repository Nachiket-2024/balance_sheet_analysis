import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const dirname = path.dirname(fileURLToPath(import.meta.url));

function preloadStylesheet() {
  return {
    name: 'preload-stylesheet',
    transformIndexHtml: {
      order: 'post' as const,
      handler(html: string) {
        return html.replace(
          /<link rel="stylesheet" crossorigin href="([^"]+)">/,
          '<link rel="stylesheet" media="print" crossorigin href="$1"><noscript><link rel="stylesheet" crossorigin href="$1"></noscript>',
        );
      },
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const configuredApiUrl = env.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const apiOrigin = new URL(configuredApiUrl).origin;

  return {
    plugins: [
      react(),
      tailwindcss(),
      preloadStylesheet(),
    ],
    resolve: {
      // Must match the "@"/"@app" paths in tsconfig.app.json and the
      // resolve.alias in vitest.config.ts, or dev-server/build-time
      // resolution of "@/..." and "@app/..." imports diverges from what
      // typecheck/tests see.
      alias: {
        '@': path.resolve(dirname, 'src/mystic_auth'),
        '@app': path.resolve(dirname, 'src/app'),
      },
    },
    server: {
      // The development server is loopback-bound by Compose, but security
      // headers still protect browser sessions if a developer deliberately
      // forwards that port. HSTS is omitted because this server uses HTTP;
      // browsers only honor HSTS received over HTTPS.
      headers: {
        'Content-Security-Policy': `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ${apiOrigin} ws: wss:; base-uri 'self'; form-action 'self'; object-src 'none'; frame-ancestors 'none'`,
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
        'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
      },
    },
    // No custom build.rollupOptions.output.manualChunks here: a prior
    // version forced every node_modules import into one "vendor" chunk for
    // better long-term caching (rarely-changing third-party code under a
    // stable hash, separate from app code that changes every deploy). That
    // broke production: app/src files like api/axiosInstance.ts both import
    // from and get imported by that vendor chunk, and Rollup placed shared
    // CJS-interop helpers into axiosInstance's own chunk, creating a real
    // circular chunk dependency. ESM's live-binding semantics for circular
    // imports meant vendor.js called a binding from axiosInstance.js's chunk
    // before that chunk's module body had run far enough to define it,
    // throwing "TypeError: t is not a function" at the very top of the
    // vendor bundle: the whole app failed to mount, a blank page with no
    // build-time warning. Reverting to Rollup's own automatic chunking
    // (its default module-graph analysis doesn't create this circular
    // dependency) trades away that caching optimization for a build that
    // actually works; re-introduce chunking later only with real production
    // verification (not just curl on the built files) that nothing crashes.
    build: {
      rollupOptions: {
        output: {
          // The translation registry intentionally initializes every supported
          // language synchronously before first paint. Keep that behavior, but
          // place each language's JSON resources in its own stable chunk so a
          // large translation registry does not become one oversized shared
          // asset. This is deliberately narrower than vendor chunking and does
          // not split application modules across unrelated execution chunks.
          manualChunks(id) {
            const match = id.match(/[\\/]translations[\\/]languages[\\/]([^\\/]+)[\\/]/);
            return match ? `i18n-${match[1]}` : undefined;
          },
        },
      },
    },
  };
});
