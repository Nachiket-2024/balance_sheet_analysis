import { translations } from "../sdk";

import en from "../../mystic_auth/translations/languages/en/status_pages.json";
import hi from "../../mystic_auth/translations/languages/hi/status_pages.json";
import mr from "../../mystic_auth/translations/languages/mr/status_pages.json";
import gu from "../../mystic_auth/translations/languages/gu/status_pages.json";

// The 404/403 pages are app-owned, so their copy doesn't belong in the
// upstream NAMESPACES list. addResourceBundle registers this namespace here
// instead. Imported once for its side effect, same pattern as
// registerLandingTranslations.ts.
for (const [lang, resource] of [
    ["en", en],
    ["hi", hi],
    ["mr", mr],
    ["gu", gu],
] as const) {
    translations.addResourceBundle(lang, "status_pages", resource);
}
