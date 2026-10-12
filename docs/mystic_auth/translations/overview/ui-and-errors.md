# Translations: Language Store, Toggle, and Backend Error Codes

---

## 3. The language store: `frontend/src/mystic_auth/store/languageStore.ts`

A small Zustand store (the same pattern as `store/themeStore.ts` for dark/light mode), persisted to
`localStorage` under the `"language"` key. It's built around a `LanguageMode` (what the user picks)
which resolves to **two separate languages**:

```ts
export const LANGUAGE_MODES = ["en", "hi", "mr", "gu", "en+hi", "en+mr", "en+gu"] as const;
export type LanguageMode = (typeof LANGUAGE_MODES)[number];

interface ResolvedLanguages {
    chromeLanguage: SupportedLanguage; // Navbar + Sidebar + dates/month names
    pageLanguage: SupportedLanguage;   // Everything else (drives the global translation language)
}
```

| Mode | `chromeLanguage` | `pageLanguage` |
|---|---|---|
| `en` | `en` | `en` |
| `hi` | `hi` | `hi` |
| `mr` | `mr` | `mr` |
| `gu` | `gu` | `gu` |
| `en+hi` | `en` | `hi` |
| `en+mr` | `en` | `mr` |
| `en+gu` | `en` | `gu` |

---

`pageLanguage` drives the translation library's global active language (`translations.changeLanguage(pageLanguage)`),
so every ordinary `useTranslation()` call across the app follows it automatically - no per-component
change needed. `chromeLanguage` is consumed explicitly by three call sites:

- **`layout/app_layout/Navbar.tsx`** and **`layout/app_layout/Sidebar.tsx`** - instead of `useTranslation("layout")`
  (which would follow `pageLanguage`), they call
  `translations.getFixedT(chromeLanguage, "layout")` to get a translator pinned to
  `chromeLanguage` regardless of what the page is doing.
- **Every page that formats a date or month name** (`DashboardPage`, `ActiveSessionsCard`,
  `UserAccessDialog`'s Details tab, the audit-log sections, `LoginTrendChart`'s day/axis labels) reads
  `chromeLanguage` from the store and passes it into `formatMemberSince`/`formatDateTime`/
  `formatTimeOnly`/`monthNameShort`, so a date reads "15 Jan 2026" in the `en+hi` mode even though
  the surrounding page text is in Hindi. Plain numeral formatting that isn't a date (pagination
  page numbers, table row indices, stat-tile counts, cooldown-timer seconds) is **not** treated
  this way - it stays on `pageLanguage`, so those numerals do translate in the mixed modes.

`document.documentElement.lang` is set to `pageLanguage` (the majority-content language), not
`chromeLanguage` - there's no single correct value for a mixed-language document, and most
assistive tech cares most about the page's actual content.

---

## 4. The toggle itself: `frontend/src/mystic_auth/layout/controls/LanguageToggle.tsx`

- A plain click-to-open dropdown (the app's `StyledSelect.tsx` component), not a typeable search box.
- Styled to match `ThemeToggle`'s icon-button look (same border/background/hover colors, with shared button variants in `ui/buttons/button-variants.ts`) via its own `Select.Trigger` overrides.
- With only seven options, a search box isn't earning its keep the way it would past a few dozen languages - this matches how most real-world language switchers (GitHub, Wikipedia, Google) work at this scale.
- Click to open, click an option, closes; the current selection stays visible on the trigger at rest either way.

---

## 5. Backend error codes: `frontend/src/mystic_auth/api/apiError.ts`

Most text in the app is translated at the point it's rendered, via `useTranslation()` in the
component itself. Backend error messages are the one exception: they're translated in a single
shared place instead, because a mutation's catch block doesn't know in advance which of several
possible backend errors it's handling.

`backend/mystic_auth/core/errors.py`'s `AppError` (see [Backend Architecture](../../architecture/backend.md))
carries a stable, machine-readable `code` (e.g. `"INVALID_CREDENTIALS"`) and optional `params`
alongside the English `detail` FastAPI/Sentry/logs see. The actual `code` -> `errors:<code>` lookup
lives in `apiError.ts`'s `translateErrorCode(code, params)`, a standalone function (not axios-shaped)
so any caller with a bare code, not just an API response, can reuse the exact same lookup and
DEV-mode missing-translation warning. `extractApiErrorMessage()` is its main caller, for ordinary
axios mutation errors:

1. If the response has a `code`, `translateErrorCode` looks it up as `errors:<code>` in the `errors`
   namespace (`translations/languages/*/errors.json`) and renders it in the caller's current
   language, interpolating `params` (e.g. a policy name into `"Policy \"{{name}}\" not found"`).
2. If there's no `code` (a route not yet migrated to `AppError`) or the code has no matching
   `errors.json` entry, fall back to the raw English `error`/`detail` string from the response
   body, so a caller never sees a blank or broken message.
3. If neither exists at all (a network failure, or a non-axios error), fall back to the
   caller-supplied `fallback` argument.

The other caller is `OAuth2LoginButton.tsx`: the OAuth2 flow is a full-page redirect back to
`/login?error=<CODE>` rather than an API response (see [Google OAuth2 / PKCE](../../authentication/oauth2-pkce.md#edge-cases--error-handling)),
so it calls `translateErrorCode` directly on that query param instead of going through
`extractApiErrorMessage`.

Case 2's "code exists but no translation" branch is the one to watch:

- It degrades gracefully for the *user* (still a real English sentence, not a blank toast).
- That same graceful degradation means a missing `errors.json` entry looks identical to "working as intended" at a glance - nothing crashes, nothing looks obviously wrong.
- So in addition to the fallback, that branch also logs a `console.error` naming the missing code, but only when `import.meta.env.DEV` is true: loud enough to catch the gap the first time you exercise that code path in development, without affecting real users or shipping a console.error into production.
- If you add a new machine-readable code - a new `AppError(code="...")` call site, or a new OAuth2 redirect code - add the matching `errors:<code>` key to all four `errors.json` files in the same change, or expect to see that warning the first time your route returns it locally.

---

See [Translations](README.md) for the feature overview, or [Setup and Formatting](setup-and-formatting.md) for translation setup and date/numeral formatting.

---
