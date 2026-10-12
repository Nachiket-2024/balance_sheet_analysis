import { translations } from "../sdk";

import en from "../../mystic_auth/translations/languages/en/legal.json";
import hi from "../../mystic_auth/translations/languages/hi/legal.json";
import mr from "../../mystic_auth/translations/languages/mr/legal.json";
import gu from "../../mystic_auth/translations/languages/gu/legal.json";

// The legal pages are app-owned: their content is deployment-specific and
// meant to be rewritten per project, so it doesn't belong in the upstream
// NAMESPACES list in mystic_auth/translations/translations.ts.
// addResourceBundle registers this "legal" namespace here instead.
// Imported once for its side effect (PrivacyPolicyPage.tsx/TermsOfServicePage.tsx
// import this module before they render), same pattern as
// app/translations/registerLandingTranslations.ts.
for (const [lang, resource] of [
    ["en", en],
    ["hi", hi],
    ["mr", mr],
    ["gu", gu],
] as const) {
    translations.addResourceBundle(lang, "legal", resource);
}
