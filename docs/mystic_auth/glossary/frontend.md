# Glossary: Frontend
---

Frontend libraries and UI patterns. See [Glossary](README.md) for the full index.

---

## shadcn/ui

The frontend's component patterns and generated UI primitives, built on Tailwind CSS and Radix UI. Theme tokens live in CSS custom properties and generate a full brand color scale from a single chosen color, both as an app-wide default and a per-user override. See [Appearance: Brand Color and Logo](../appearance/overview.md).

---

## Zustand

A small React state-management library used for the frontend's client-side stores (e.g. `authStore`, which holds the signed-in user's profile and permissions, never any token). Tokens themselves never touch it since they only ever live in httpOnly cookies.

---

## TanStack Query

The frontend's library for fetching, caching, and re-fetching server data (e.g. `useCurrentUserQuery`, `useSessionsQuery`). Its cache is what gets invalidated or reset when a real-time push event (like a revoke or a permissions change) arrives.

---

## Axios

The HTTP client library the frontend uses to call the backend API, wrapped in one shared instance (`axiosInstance.ts`) plus a typed function per backend domain (`auth_api`, `users_api`, and so on).

---

## SPA (Single-Page Application)

A frontend architecture where the browser loads one HTML page and JavaScript handles all navigation and rendering afterward, without full page reloads. This app's frontend (React 19 + TypeScript + Vite) is a SPA; the backend serves it as a static build in production. See [Frontend Architecture](../architecture/frontend.md).

---

## command palette

A keyboard-triggered (Cmd/Ctrl+K) search-and-jump UI in the frontend for quickly navigating to pages or actions without clicking through menus. It respects the same permission checks as the pages it links to, so it never surfaces something the current user can't actually open. See [Frontend Customization](../template-usage/frontend-customization.md).

---

## brand mark

The visible app logo area rendered by `Logo.tsx` in the sidebar and auth
layout. By default it is an icon plus `APP_NAME`. Setting
`VITE_APP_LOGO_URL` makes it render that image instead. This is separate from
the browser favicon, which uses `public/favicon.svg` until a signed-in user
picks a per-user brand color. See [Appearance: Brand Color and Logo](../appearance/overview.md).

---

## gate component (`IfCan`, `ProtectedRoute`, `Authorized`)

A frontend React component that conditionally renders its children (or redirects) based on the current user's permissions, mirroring the backend's PBAC checks so the UI never shows a control the user isn't actually allowed to use. This is a UI convenience only; the server still independently enforces every action. See [Frontend Architecture: Module tour](../architecture/frontend.md#module-layout).

---

## lazy route / code-splitting

Loading a page's JavaScript only when the user actually navigates to it, instead of bundling the whole app into one download. This app shows a progress bar and skeleton state while a lazy route's chunk is still loading. See [Frontend Architecture](../architecture/frontend.md).

---
