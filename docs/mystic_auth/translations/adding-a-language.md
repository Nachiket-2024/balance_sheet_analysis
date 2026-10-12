# Tutorial: Adding a New Language
---

See [Translations Overview](overview/README.md) for the architecture (translation setup, date/numeral
formatting, the language store, the toggle, and backend error codes) this tutorial builds on.

---

Say you want to add Tamil (`ta`). Every step below is additive - nothing here requires touching
component logic, only data files (plus the four language-scoped modules).

This walkthrough changes the template's built-in language set, so it is for
upstream/template contributors. A downstream project must not edit
`frontend/src/mystic_auth/` to add a language. App-owned pages can add their
own namespace with `translations.addResourceBundle`, as the existing files in
`frontend/src/app/translations/` demonstrate; adding a language to the shared
MysticAuth shell requires an upstream contribution (or a deliberate frontend
replacement).

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    S1["1. Add the language code\ntranslations.ts"]
    S2["2. Add the 12 shared locale files"]
    S3["3. Add month names\nmonthNames.ts"]
    S4["4. Add digit glyphs\nnumerals.ts (or null for ASCII)"]
    S5["5. Add time-of-day formatting\ntimeOfDay.ts"]
    S6{"6. Optional: mixed\n'English + language' modes?"}
    S6a["Add to LANGUAGE_MODES,\nLANGUAGE_MODE_LABELS,\nresolveLanguages()\nlanguageStore.ts"]
    S7["7. Verify: typecheck,\nrun the test suite,\ncheck it live"]

    S1 --> S2 --> S3 --> S4 --> S5 --> S6
    S6 -- "yes" --> S6a --> S7
    S6 -- "no" --> S7

    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class S6 decision
    class S7 terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

Every `Record<SupportedLanguage, ...>` across steps 1-5 is a compile-time exhaustiveness check, so a
missing entry in any of them fails `npm run typecheck` rather than shipping a silent runtime gap.

---

## 1. Add the language code

`frontend/src/mystic_auth/translations/translations.ts`:

```ts
export const SUPPORTED_LANGUAGES = ["en", "hi", "mr", "gu", "ta"] as const;

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
    en: "English",
    hi: "हिंदी",
    mr: "मराठी",
    gu: "ગુજરાતી",
    ta: "தமிழ்",
};
```

---

## 2. Add a locale folder with the twelve shared namespace files

Copy the twelve shared files from `frontend/src/mystic_auth/translations/languages/en/` to a new
`languages/ta/` folder (`ui_text.json`, `layout.json`, `auth.json`, `users.json`, `policies.json`,
`permissions.json`, `authorization.json`, `audit_log.json`, `account_settings.json`, `dashboard.json`,
`rate_limits.json`, and `errors.json`), then translate every value - keep every key identical to the
English source, only the values change. Missing keys silently fall back to
`fallbackLng: "en"` (see `translations.ts`'s `i18next.init()` call), so a partial translation
degrades gracefully rather than crashing, but treat that as a to-do, not a shipped state. (The
`i18next.init()` call referenced above is `react-i18next`'s own API name; this repo's wrapper
around it is `translations.ts`.)

Then import and register the twelve shared files in `translations.ts`, following the existing `hi`/`mr`/`gu`
blocks:

```ts
import taUiText from "./languages/ta/ui_text.json";
import taLayout from "./languages/ta/layout.json";
// ...the other ten shared namespaces

// inside translations.use(initReactI18next).init({ resources: { ... } }):
ta: {
    ui_text: taUiText,
    layout: taLayout,
    // ...the other ten shared namespaces
},
```

The three app-content files (`landing.json`, `status_pages.json`, and `legal.json`) are separate
from this shared registration. If the downstream app uses those pages, add the Tamil JSON files and
extend the corresponding app-owned registration modules under `frontend/src/app/translations/`.
Do not add those namespaces to `mystic_auth/translations/translations.ts`.

---

## 3. Add month names

`frontend/src/mystic_auth/translations/monthNames.ts`:

```ts
const MONTH_NAMES_SHORT: Record<SupportedLanguage, readonly string[]> = {
    en: [...], hi: [...], mr: [...], gu: [...],
    ta: ["ஜன", "பிப்", "மார்", "ஏப்", "மே", "ஜூன்", "ஜூலை", "ஆக", "செப்", "அக்", "நவ", "டிச"],
};
```

---

## 4. Add digit glyphs (if the language uses non-ASCII numerals)

`frontend/src/mystic_auth/translations/numerals.ts` - add a new digit map (or reuse an existing one,
the way `hi`/`mr` both point at the same `DEVANAGARI_DIGITS` object) if the script has its own
digits, or `null` to keep ASCII digits:

```ts
const DIGIT_MAPS: Record<SupportedLanguage, Record<string, string> | null> = {
    en: null, hi: DEVANAGARI_DIGITS, mr: DEVANAGARI_DIGITS, gu: GUJARATI_DIGITS,
    ta: null, // or a TAMIL_DIGITS map, following the DEVANAGARI_DIGITS/GUJARATI_DIGITS shape
};
```

---

## 5. Add time-of-day formatting

`frontend/src/mystic_auth/translations/timeOfDay.ts` - add a locale tag, and decide whether the
language uses AM/PM-style or day-period-word formatting (see the `hi`/`mr`/`gu` branch vs. the `en`
branch in `formatHourMinute`):

```ts
const LOCALE_TAGS: Record<SupportedLanguage, string> = {
    en: "en-US", hi: "hi-IN", mr: "mr-IN", gu: "gu-IN", ta: "ta-IN",
};
```

If the new language should show a literal AM/PM (like English) rather than native day-period words,
add its code to that function's `language === "en"` branch condition instead of falling through to
the `Intl.DateTimeFormat(..., { dayPeriod: "short" })` branch.

---

## 6. (Optional) Add mixed "English + `<language>`" modes

Only needed if you want the same chrome-English/page-translated split this repo already offers for
Hindi, Marathi, and Gujarati. In `frontend/src/mystic_auth/store/languageStore.ts`:

```ts
export const LANGUAGE_MODES = [
    "en", "hi", "mr", "gu", "ta", "en+hi", "en+mr", "en+gu", "en+ta",
] as const;

export const LANGUAGE_MODE_LABELS: Record<LanguageMode, string> = {
    // ...existing entries
    ta: "தமிழ் (Tamil)",
    "en+ta": "English + தமிழ்",
};

function resolveLanguages(mode: LanguageMode): ResolvedLanguages {
    switch (mode) {
        // ...existing cases
        case "ta":
            return { chromeLanguage: "ta", pageLanguage: "ta" };
        case "en+ta":
            return { chromeLanguage: "en", pageLanguage: "ta" };
    }
}
```

`LanguageToggle.tsx` needs no changes - it renders `LANGUAGE_MODES` generically, so the new options
just appear.

---

## 7. Verify

- `npm run typecheck --prefix frontend` - every `Record<SupportedLanguage, ...>` above is a
  compile-time exhaustiveness check, so a missing entry in any of the four modules is a type error,
  not a silent runtime gap.
- `npm run test --prefix frontend` - run the existing suite; `tests/frontend/mystic_auth/unit/store/languageStore.test.ts`
  and `tests/frontend/mystic_auth/unit/layout/controls/LanguageToggle.test.tsx` cover the store/toggle
  mechanics generically enough that they don't need new cases for a new language, only for a new
  *mixed mode* if you added one in step 6.
- Run the app (`npm run dev --prefix frontend`), open the language toggle, and check a page with
  dates (Dashboard) and a page with forms (Account Settings) in the new language and, if added, its
  mixed mode.

---

## Where to go next

- [Translations Overview](overview/README.md): the architecture this tutorial builds on.
- [Frontend Architecture](../architecture/frontend.md): how `translations/`, `store/`, and `layout/`
  fit into the rest of the frontend module layout.
- [Testing Overview](../testing/overview.md): how to run the frontend Vitest suite this doc's
  verification step above uses.

---
