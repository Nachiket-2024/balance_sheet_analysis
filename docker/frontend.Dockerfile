# Runs the Vite dev server with HMR — used by docker-compose.yml for local
# development. This is the default build target so existing `docker compose
# build`/`up` (no --target flag) keeps working unchanged.
#
# Intentionally stays root (unlike the `production` stage below, which runs
# as non-root `nginx`). This stage `npm install`s into a bind-mounted
# `frontend/`, and pinning it to a non-root UID would fight host/container
# UID mismatches on that mount across different host OSes instead of just
# working out of the box.
FROM node:22.23.2-bullseye AS dev

WORKDIR /app

# Required to compile native optional dependencies for Rollup / esbuild
RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# Produces the static production bundle (frontend/dist). Only reached when
# building with --target production (or production's stage below, which
# depends on it) — docker-compose.yml's dev service never builds this far.
FROM node:22.23.2-bullseye AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ .

# VITE_* vars are inlined into the static bundle at build time, so unlike
# the dev target (no frontend/.env bind mount here) they arrive as build
# args, wired from docker-compose.prod.yml / repo root .env. Re-exporting
# ARG as ENV is required for `vite build`'s child process to see them —
# ARG alone isn't inherited by RUN's subprocesses. None of these are
# secrets: all four end up readable in the shipped JS bundle regardless.
ARG VITE_API_BASE_URL
ARG VITE_APP_NAME
ARG VITE_SENTRY_DSN
ARG VITE_SENTRY_ENVIRONMENT
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_NAME=${VITE_APP_NAME} \
    VITE_SENTRY_DSN=${VITE_SENTRY_DSN} \
    VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT}

RUN npm run build

# Serves the static build via nginx — no Node.js, no dev dependencies, no
# source maps of the toolchain, just the compiled assets. Used by
# docker-compose.local-prod.yml and docker-compose.prod.yml via
# `build.target: production`.
FROM nginx:1.27-alpine AS production

COPY docker/nginx.frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx:alpine ships an unprivileged "nginx" user and already-writable
# runtime dirs for it. nginx-unprivileged patterns are unnecessary because
# the stock image supports running as non-root out of the box.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/run \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid
USER nginx

EXPOSE 80

# 127.0.0.1, not localhost: default.conf is root-owned (only
# /usr/share/nginx/html, /var/cache/nginx, and /var/run are chowned to
# nginx above), so the base image's IPv6-listen entrypoint script can't
# patch it to add a `listen [::]:80` directive and silently no-ops, leaving
# nginx IPv4-only. "localhost" resolves to ::1 first in this container, so
# it hits connection-refused even though nginx is up and serving on IPv4.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD wget -qO- http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
