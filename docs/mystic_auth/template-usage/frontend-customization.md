# Frontend Customization
---

See [Using This Repository as a Template](overview.md) for the full overview (ownership tiers,
quickstart, backend customization, deployment, and more). This page covers frontend customization
specifically: the pieces you edit directly, and the shared-chrome extension points for the pieces
you can't.

---

## Frontend customization

- **Theme**: just changing the brand color? Set `BRAND_COLOR` in the active runtime env file (normally `env/mystic_auth/.env.dev` for dev; downstream-only overrides belong in `env/app/`) (aliased to `VITE_BRAND_COLOR`, same pattern as `APP_NAME`), no code edit needed - see [Appearance: Default brand color](../appearance/overview.md#default-brand-color). For anything beyond a single color, `frontend/src/app/theme.ts` (empty by default, like `app_sdk.ts`) exports `brandColor`/`cssVars` overrides that `mystic_auth/theme/applyBrandCssVars.ts` applies on top of `theme/tailwind.css`'s own CSS custom properties at startup, so neither ever needs editing directly. Either way this is the app-owner-level default; end users can additionally pick their own per-account brand color from Account Settings (`account_settings/AppearanceCard.tsx`, backed by `store/appearanceStore.ts` and `theme/generateBrandScale.ts`), which overrides this default client-side for that signed-in user only.
- **Pages**: `frontend/src/mystic_auth/` is organized one folder per feature (`auth/`, `dashboard/` (which includes session management), `account_settings/`, `users/`, `policies/`, `audit_log/`, `authorization/`, `rate_limits/`, `legal/`). See [Frontend Architecture](../architecture/frontend.md#module-layout).
- **Routing**: declared in `frontend/src/app/App.tsx`: add a `<Route>`, wrapped in `ProtectedRoute`.
- **State**: Zustand (`frontend/src/mystic_auth/store/`) for client state, TanStack Query for server state: both re-exported from `sdk.ts`.
- **Your own code** lives under `frontend/src/app/` (e.g. `frontend/src/app/projects/`), importing template pieces via `sdk.ts`/`app_sdk.ts`.

---

## Shared-chrome extension points

Some UI, like the sidebar, is rendered by mystic_auth/ but genuinely needs to reflect your own feature routes: "never edit mystic_auth/" can't mean "never add your own nav link." Rather than leaving that as a choice between hand-editing an upstream-owned file or having no nav link at all, the shared-chrome components that need this take an explicit prop for it:

---

| Component | Extension prop | Shape |
|---|---|---|
| `AppLayout` (re-exported from `sdk.ts`) | `extraNavItems?: NavItem[]` | `NavItem` (also re-exported from `sdk.ts`): `{ label: string; to: string; permission?: string; order?: number; icon?: LucideIcon }` |
| `AppLayout` (re-exported from `sdk.ts`) | `extraNavbarContent?: React.ReactNode` | Any renderable node: the top bar's own built-ins (name, ThemeToggle, LogoutButton) are bespoke components rather than a uniform list, so this slot is free-form instead of a typed item array. |
| `CommandPalette` (re-exported from `sdk.ts`, mounted once in `App.tsx`) | `extraNavItems?: NavItem[]` | Same `NavItem`s you give `AppLayout` - pass the same reference so the palette's "Pages" results match the sidebar. |
| `CommandPalette` (re-exported from `sdk.ts`, mounted once in `App.tsx`) | `extraSearchItems?: SearchItem[]` | `SearchItem` (also re-exported from `sdk.ts`): a specific feature/section *within* one of your pages (not a whole page - that's what `extraNavItems` is for), surfaced by the palette's content search once the query is non-empty. |
| `AppLayout` (re-exported from `sdk.ts`) | `onOpenCommandPalette?: () => void` | Renders the clickable "search" button in the navbar (hidden below the `md` breakpoint) that opens the same `CommandPalette` instance. Cmd+K/Ctrl+K works without it (that shortcut is wired globally in `App.tsx`); omitting this prop just means there's no visible button for it, mouse-only users would have no way to open the palette. |
| `AuditLogPage` (imported directly in `App.tsx`, like any other page) | `extraResourceTypes?: string[]` | Appended after this app's own `AUTHORIZATION_RESOURCE_TYPES` in the "Authorization decisions" filter's resource dropdown. |
| `AuditLogPage` (imported directly in `App.tsx`, like any other page) | `extraActions?: string[]` | Appended after `PERMISSIONS`' own action strings in the same filter's action dropdown. |

---

Pass the same array to every `<AppLayout>` usage in your `App.tsx` (define it once, above your `<Routes>`, and reuse the reference) so the sidebar doesn't reshape as the user navigates between routes:

```tsx
import { AppLayout, type NavItem } from "./sdk";
import { APP_PERMISSIONS } from "./access/permissions"; // your own action vocabulary

const EXTRA_NAV_ITEMS: NavItem[] = [
    { label: "Projects", to: "/projects", permission: APP_PERMISSIONS.PROJECTS_READ },
];

// ...
<AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
    <ProjectsPage />
</AppLayout>
```
---

Items with a `permission` are gated the same way the built-in nav items are (wrapped in `IfCan`), so a caller who lacks it simply doesn't see the link, the same as any built-in one. Omitting `extraNavItems` entirely renders the sidebar exactly as before this prop existed, so adopting it (or upgrading a project that predates it) is never a breaking change.

---

**Ordering.** By default your items render *after* every built-in one (Dashboard, Users, Policies, Audit Log, Account Settings), in the order you list them. That's what happens if you don't set `order` at all, so leaving it out is never a breaking change either. To interleave with the built-ins instead, give an item an `order` number: the built-ins are `10`/`20`/`30`/`40`/`50` (see `frontend/src/mystic_auth/layout/app_layout/navItems.ts`), spaced out so you can slot in between any two without needing to know anyone else's exact value.

```tsx
const EXTRA_NAV_ITEMS: NavItem[] = [
    // Lands between Dashboard (10) and Users (20)
    { label: "Projects", to: "/projects", order: 15, permission: APP_PERMISSIONS.PROJECTS_READ },
];
```

Items sharing the same `order` (or all omitting it) keep their relative order from the array they were given in: ties never get shuffled.

---

**Top bar.** `extraNavbarContent` renders wherever you pass it, to the left of ThemeToggle/LogoutButton, no permission gating or ordering of its own since it's a single free-form slot rather than a list:

```tsx
import { AppLayout } from "./sdk";
import NotificationsBell from "./notifications/NotificationsBell";

// ...
<AppLayout extraNavItems={EXTRA_NAV_ITEMS} extraNavbarContent={<NotificationsBell />}>
    <ProjectsPage />
</AppLayout>
```

---

**Command palette (Cmd+K / Ctrl+K).** `CommandPalette` is mounted once at the app root in `App.tsx`, not inside `AppLayout`, so it takes its extension props there instead. Pass the same `onOpenCommandPalette` handler to every `<AppLayout>` so the navbar's search button opens this one instance:

```tsx
const [isPaletteOpen, setIsPaletteOpen] = useState(false);
const openCommandPalette = () => setIsPaletteOpen(true);

// ...
<AppLayout extraNavItems={EXTRA_NAV_ITEMS} onOpenCommandPalette={openCommandPalette}>
    <ProjectsPage />
</AppLayout>

<CommandPalette
    isOpen={isPaletteOpen}
    onClose={() => setIsPaletteOpen(false)}
    extraNavItems={EXTRA_NAV_ITEMS}
    extraSearchItems={EXTRA_SEARCH_ITEMS}
/>
```

---

`extraNavItems` is the exact same array you already pass to every `<AppLayout>` - reusing it keeps the palette's "Pages" results and the sidebar in sync automatically. `extraSearchItems` is for content search: a specific settings tab, a specific filtered view, anything a user might type a keyword for that isn't a whole page's own nav label. Each `SearchItem` is:

```ts
interface SearchItem {
    label: string;              // primary display text
    detail?: string;            // secondary text, e.g. distinguishes two items sharing a label
    group: string;              // the page/section this belongs to - shown as detail's fallback,
                                 // and folded into the search text (typing the page name matches too)
    matchKeys?: string[];       // extra strings folded into search text without being displayed
    to: string;                 // destination, e.g. "/projects?tab=billing" or "/projects#danger-zone"
    permission?: string;
    icon?: LucideIcon;
}
```
---

`label`/`detail`/`group`/`matchKeys` each accept either a plain string or an i18next `"namespace:key"` (resolved in the chrome language, same convention `NavItem.label` uses) - use translation keys if your app is localized, plain strings otherwise. A result's search text is `label + detail + group + matchKeys` joined, so you don't need to hand-maintain a separate keyword list in sync with whatever visible copy you're already reusing:

```tsx
import { CommandPalette, type SearchItem } from "./sdk";
import { CreditCard } from "lucide-react";

const EXTRA_SEARCH_ITEMS: SearchItem[] = [
    {
        label: "Billing",
        group: "Projects",
        matchKeys: ["Invoices", "Payment method"],
        to: "/projects?tab=billing",
        icon: CreditCard,
    },
];
```

---

For a `to` that points at a specific tab (`?tab=billing`) or a specific in-page section (`#danger-zone`), your page needs to actually read that on mount - see `AccountSettingsPage`/`AuditLogPage` for the query-param-driven-tab pattern (read once via `useSearchParams`, force a remount with `key={initialTab}` so a later deep-link while the page is already open still switches tabs), or `AppLayout`'s `useScrollToHash` for the `#hash` case (mounted once in `AppLayout` already, so any element with a matching `id` on any of your pages gets scrolled to automatically - just give it an `id`, no extra wiring needed). Omitting `extraSearchItems` entirely renders the palette exactly as before this prop existed.

---

**Audit log filters.** Unlike `AppLayout`, `AuditLogPage` isn't behind `sdk.ts`: it's a page component, imported directly in `App.tsx` the same way `DashboardPage`/`UsersPage`/`PoliciesPage` are, so you already edit that import site directly to add routes. If your app extends the PBAC resource-type or action vocabulary for its own domain (e.g. adding resource types beyond this app's own `users`/`policies`/`security_audit`), pass `extraResourceTypes`/`extraActions` so your own values show up in the "Authorization decisions" tab's filter dropdowns instead of only ever showing this app's built-in vocabulary:

```tsx
<AuditLogPage
    extraResourceTypes={["projects", "invoices"]}
    extraActions={["projects:read", "projects:write"]}
/>
```

Omitting either prop renders both dropdowns exactly as before these props existed.

If a future release adds an extension point to another shared component, it'll follow this same shape: a typed, optional, additive prop, listed in this table.

---

## Where to go next

- [Using This Repository as a Template](overview.md): ownership tiers, quickstart, backend
  customization, and deployment.
- [Worked Example: Adding a New Domain, End to End](worked-example.md): wires `extraNavItems` and
  the rest of the pieces above together for one fake domain.

---