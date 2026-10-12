// This app's own translation resources, registered into the same i18next
// singleton mystic_auth/translations/translations.ts already initializes
// (`i18next`'s default export is a shared module-level instance, so this
// import gets the exact same configured object, not a separate one).
// Deliberately not a file under mystic_auth/ and not an edit to that file:
// see docs/mystic_auth/translations/overview.md and
// docs/app/architecture/conventions.md for why app-owned namespaces are
// added this way, via addResourceBundle, instead of hand-editing the
// upstream-owned resources map.
import i18next from "i18next";

import enCompanies from "./languages/en/companies.json";
import enBalanceSheets from "./languages/en/balance_sheets.json";
import enLlm from "./languages/en/llm.json";
import enErrors from "./languages/en/errors.json";
import enAnalysis from "./languages/en/analysis.json";

import hiCompanies from "./languages/hi/companies.json";
import hiBalanceSheets from "./languages/hi/balance_sheets.json";
import hiLlm from "./languages/hi/llm.json";
import hiErrors from "./languages/hi/errors.json";
import hiAnalysis from "./languages/hi/analysis.json";

import mrCompanies from "./languages/mr/companies.json";
import mrBalanceSheets from "./languages/mr/balance_sheets.json";
import mrLlm from "./languages/mr/llm.json";
import mrErrors from "./languages/mr/errors.json";
import mrAnalysis from "./languages/mr/analysis.json";

import guCompanies from "./languages/gu/companies.json";
import guBalanceSheets from "./languages/gu/balance_sheets.json";
import guLlm from "./languages/gu/llm.json";
import guErrors from "./languages/gu/errors.json";
import guAnalysis from "./languages/gu/analysis.json";

// One namespace per feature folder under src/app/, mirroring mystic_auth's
// own convention (see docs/mystic_auth/translations/overview.md). "errors"
// is the one exception: it's merged (deep, non-overwriting) into
// mystic_auth's own already-registered "errors" namespace rather than
// creating a second one, since apiError.ts's extractApiErrorMessage() always
// looks a backend error `code` up as `errors:<code>` in that single
// namespace - see backend_app/api.md's "Error codes" section for the two
// codes this app's own get_or_404() calls raise
// (COMPANY_NOT_FOUND/BALANCE_SHEET_NOT_FOUND).
const RESOURCES: Record<string, Record<string, Record<string, string>>> = {
    en: { companies: enCompanies, balance_sheets: enBalanceSheets, llm: enLlm, errors: enErrors, analysis: enAnalysis },
    hi: { companies: hiCompanies, balance_sheets: hiBalanceSheets, llm: hiLlm, errors: hiErrors, analysis: hiAnalysis },
    mr: { companies: mrCompanies, balance_sheets: mrBalanceSheets, llm: mrLlm, errors: mrErrors, analysis: mrAnalysis },
    gu: { companies: guCompanies, balance_sheets: guBalanceSheets, llm: guLlm, errors: guErrors, analysis: guAnalysis },
};

for (const [lng, namespaces] of Object.entries(RESOURCES)) {
    for (const [ns, resources] of Object.entries(namespaces)) {
        // deep=true, overwrite=false: adds these keys alongside whatever's
        // already registered for that namespace/language (relevant for
        // "errors", which mystic_auth's own translations.ts already
        // populated) without ever clobbering an existing key.
        // i18next mutates the object passed to addResourceBundle when merging.
        // Keep the imported JSON module untouched: the shared MysticAuth
        // translation parity checks compare those source objects directly.
        if (ns === "errors") {
            // The initial MysticAuth bundle is backed by its imported JSON
            // object. Detach it before merging app error codes so i18next's
            // deep merge cannot append app-only keys to that source object.
            const existing = i18next.getResourceBundle(lng, ns) ?? {};
            i18next.removeResourceBundle(lng, ns);
            i18next.addResourceBundle(lng, ns, { ...existing, ...resources }, true, false);
        } else {
            i18next.addResourceBundle(lng, ns, { ...resources }, true, false);
        }
    }
}
