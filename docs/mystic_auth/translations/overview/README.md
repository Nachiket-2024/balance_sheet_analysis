# Translations

---

The frontend renders in multiple languages via [`react-i18next`](https://react.i18next.com/). This
doc covers what's supported today, how the moving pieces fit together, and a step-by-step
tutorial for adding a new language. See [Frontend Architecture](../../architecture/frontend.md) for
how this fits into the rest of `frontend/src/mystic_auth/`.

---

## What's supported today

| Language | Code | Native label |
|---|---|---|
| English | `en` | English |
| Hindi | `hi` | हिंदी |
| Marathi | `mr` | मराठी |
| Gujarati | `gu` | ગુજરાતી |

---

The language toggle (`LanguageToggle`, in the navbar next to the dark/light mode toggle) doesn't
just switch between these four - it offers **seven modes**:

| Mode | What renders in English | What renders in the other language |
|---|---|---|
| `en` | Everything | - |
| `hi` | - | Everything, including navbar/sidebar |
| `mr` | - | Everything, including navbar/sidebar |
| `gu` | - | Everything, including navbar/sidebar |
| `en+hi` | Navbar, sidebar, and all dates/month names | Page content (titles, forms, tables, messages) in Hindi |
| `en+mr` | Navbar, sidebar, and all dates/month names | Page content in Marathi |
| `en+gu` | Navbar, sidebar, and all dates/month names | Page content in Gujarati |

The three mixed modes exist because a caller who's more comfortable navigating in English (menus,
buttons, chrome) may still want the actual content - forms, table data, messages - in their own
language. The plain `hi`/`mr`/`gu` modes are unchanged from a normal single-language app: everything,
chrome included, switches.

---

## Architecture

- [Setup and Formatting](setup-and-formatting.md): namespaces, translation files, and date/month/numeral formatting.
- [Language Store, Toggle, and Backend Error Codes](ui-and-errors.md): the `languageStore`, the toggle UI, and how backend error codes get translated.

---

## Adding a new language

For the step-by-step walkthrough of adding a new language (Tamil, as a worked example) across every
data file this touches, see [Tutorial: Adding a New Language](../adding-a-language.md).

---

## Where to go next

- [Tutorial: Adding a New Language](../adding-a-language.md): step-by-step walkthrough of adding a new
  language.
- [Frontend Architecture](../../architecture/frontend.md): how `translations/`, `store/`, and `layout/`
  fit into the rest of the frontend module layout.
- [Testing Overview](../../testing/overview.md): how to run the frontend Vitest suite the tutorial's
  verification step uses.

---
