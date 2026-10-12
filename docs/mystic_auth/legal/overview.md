# Legal Documents and Signup Consent
---

Ships a Privacy Policy and Terms of Service as real in-app pages, written against this template's actual data flows rather than generic boilerplate, plus the consent notice that links to them from Signup. Both documents are content you're expected to review and edit before shipping to real users; see "Operator responsibility" below.

---

## Feature map

| Layer | Files | Responsibility |
|---|---|---|
| Shared layout | `frontend/src/app/legal/LegalDocumentLayout.tsx` | Presentational shell (`AuthLayout` chrome, `Logo`, title, "Last updated" date, intro paragraphs, numbered sections, a context-aware Back button). Renders whatever `title`/`intro`/`sections` it's given; doesn't know which document it's showing. |
| Pages | `frontend/src/app/legal/PrivacyPolicyPage.tsx`, `TermsOfServicePage.tsx` | Resolve the `legal` translation namespace and pass the result into `LegalDocumentLayout`. |
| Content | `frontend/src/mystic_auth/translations/languages/<lang>/legal.json` | All document text, per language. The app layer registers it as its own `legal` i18next namespace at runtime (`frontend/src/app/translations/registerLegalTranslations.ts`), outside the shared `NAMESPACES` list. It is one of three documented app-content ownership exceptions: downstream operators edit these JSON values, but do not edit the surrounding `mystic_auth` translation code. |
| Routes | `frontend/src/app/App.tsx` | `/privacy` and `/terms`, both lazy-loaded (`trackedLazy`), both public (no `ProtectedRoute` wrapper: reachable signed in or signed out). |
| Signup consent | `frontend/src/mystic_auth/auth/signup/SignupForm.tsx` | The consent line under the submit button, linking to both documents. |
| Entry points | `SignupForm.tsx`, `LoginPage.tsx`, `frontend/src/app/landing_page/LandingPage.tsx` (footer), `frontend/src/mystic_auth/account_settings/AccountSettingsPage.tsx` | Every place a link to either document is reachable from. |
| Tests | `tests/frontend/mystic_auth/unit/auth/signup_form_legal_consent.test.tsx` | Regression guard confirming the consent line links to `/terms` and `/privacy`. |

---

## Signup consent is a notice, not a gate

Signup does **not** block submission behind an unchecked consent checkbox. `SignupForm.tsx` renders a static sentence under the submit button ("By signing up, you agree to our Terms of Service and Privacy Policy," via `agreeToTermsPrefix`/`termsOfService`/`and`/`privacyPolicy` keys in the `auth` namespace), with `AuthInlineLink`s to `/terms` and `/privacy`. Creating an account is treated as acceptance by using the service, the same "notice, not a checkbox" pattern many production signup flows use, rather than an interactive consent gate with its own validation state.

`signup_form_legal_consent.test.tsx` is a regression guard specifically for this: it renders `SignupForm` and asserts both links exist with the right `href`, guarding against the line (or either link) silently disappearing, not against a missing checkbox, since there isn't one.

The same links (`AuthInlineLink to="/terms"` / `to="/privacy"`) also appear on `LoginPage.tsx`, the `LandingPage.tsx` footer, and `AccountSettingsPage.tsx`, so a visitor or an already-signed-in user can reach either document without going through Signup at all.

---

## Document structure and content

Both `PrivacyPolicyPage` and `TermsOfServicePage` follow the same shape: a `title`, an `intro` (array of paragraphs), and `sections` (array of `{ heading, paragraphs }`), all resolved from `legal.json` via `t(..., { returnObjects: true })` and typed as `LegalSection[]`. `LegalDocumentLayout` renders whatever it's given, plus a shared "Last updated" date (`lastUpdatedDate` in `legal.json`) and a Back button.

`legal.json`'s privacy policy is organized as: account data collected, session/device data (IP, user agent, geolocation, cookies), security/authorization logs, who data is shared with (Google, the SMTP relay, the error-monitoring service), retention (including that audit entries are retained in anonymized form after account purge and identifiers are removed after the configured retention period), user rights, children's privacy, and how policy changes are communicated. Its content is written to describe *this template's own actual behavior* (e.g. "we use two cookies: `access_token` and `refresh_token`, both `httpOnly`, `Secure`, and `SameSite=Strict`"; "audit entries remain after identifiers have been anonymized"), not generic placeholder legal text.

Two interpolated placeholders are deliberately left for the operator to fill in, not this template:

- `operatorContactPlaceholder`: a real support contact email, interpolated into the privacy policy's "Your rights" section and the terms' "Contact" section.
- `operatorEntityPlaceholder`: a legal entity name and jurisdiction, interpolated into the terms' "Governing law" section.

Both default to bracketed placeholder text (e.g. `[operator: replace with your support contact email]`) so an unedited deployment reads obviously unfinished rather than silently wrong.

---

## Operator responsibility

`legal.json` itself carries an `operatorReviewNote` key stating this directly: the content describes the software's actual behavior as built, not generic boilerplate, but if you're the operator deploying this template, review it against your own use case before publishing it as a live policy. Concretely, before shipping to real users:

1. Replace `operatorContactPlaceholder` and `operatorEntityPlaceholder` (and any other bracketed placeholder) in every language's `legal.json`.
2. Re-read both documents against what your actual deployment does: if you've disabled a feature (e.g. session geolocation, error monitoring) or added your own data collection, the shipped text will be wrong until you edit it to match.
3. Update `lastUpdatedDate` when you materially change either document, the same convention the shipped copy already documents in its own "Changes to this policy"/"Changes to these terms" sections.
4. `legal.json` is one of three documented exceptions to the normal path-based ownership rule: it remains beside the shared language files so language completeness stays easy to verify, but its values are downstream-owned deployment content. An upstream sync may change the same file; if that happens, preserve reviewed legal text and manually incorporate any new keys before testing. See [The `app/` + `mystic_auth/` Split](../template-usage/ownership-split.md#one-intentional-content-exception-three-namespaces) and [Staying in Sync with Upstream Template Updates](../template-usage/syncing-upstream/README.md).

---

## Adding a language

`legal.json` is one of the three app-content namespaces (see [Translations Overview](../translations/overview/README.md)); adding a language means adding a `legal.json` for it, following the same `title`/`intro`/`sections` shape as the English version, alongside every other namespace file the [language tutorial](../translations/adding-a-language.md) walks through.

---

## Where to go next

- [Translations Overview](../translations/overview/README.md): how the `legal` namespace fits into the rest of the translation system.
- [Signup and Email Verification](../authentication/signup-and-verification.md): the rest of the signup flow this consent notice is part of.

---
