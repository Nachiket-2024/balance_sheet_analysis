import { translations } from "../sdk";

import en from "../landing_page/translations/en.json";
import hi from "../landing_page/translations/hi.json";
import mr from "../landing_page/translations/mr.json";
import gu from "../landing_page/translations/gu.json";

// LandingPage is app-owned, so its copy doesn't belong in the upstream
// NAMESPACES list in mystic_auth/translations/translations.ts. addResourceBundle
// registers this "landing" namespace here instead. Imported once for its
// side effect (LandingPage.tsx imports this module before it renders).
for (const [lang, resource] of [
    ["en", en],
    ["hi", hi],
    ["mr", mr],
    ["gu", gu],
] as const) {
    translations.addResourceBundle(lang, "landing", resource);
}
