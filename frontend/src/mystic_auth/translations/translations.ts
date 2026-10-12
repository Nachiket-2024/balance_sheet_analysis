import translations from "i18next";
import { initReactI18next } from "react-i18next";

import enUiText from "./languages/en/ui_text.json";
import enLayout from "./languages/en/layout.json";
import enAuth from "./languages/en/auth.json";
import enUsers from "./languages/en/users.json";
import enPolicies from "./languages/en/policies.json";
import enPermissions from "./languages/en/permissions.json";
import enAuthorization from "./languages/en/authorization.json";
import enAuditLog from "./languages/en/audit_log.json";
import enAccountSettings from "./languages/en/account_settings.json";
import enDashboard from "./languages/en/dashboard.json";
import enRateLimits from "./languages/en/rate_limits.json";
import enErrors from "./languages/en/errors.json";

// One namespace per feature folder under src/mystic_auth/, so translation
// files stay small and map to code ownership instead of one giant JSON.
export const NAMESPACES = [
    "ui_text",
    "layout",
    "auth",
    "users",
    "policies",
    "permissions",
    "authorization",
    "audit_log",
    "account_settings",
    "dashboard",
    "rate_limits",
    "errors",
] as const;

export type Namespace = (typeof NAMESPACES)[number];

export const SUPPORTED_LANGUAGES = ["en", "hi", "mr", "gu"] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
    en: "English",
    hi: "हिंदी",
    mr: "मराठी",
    gu: "ગુજરાતી",
};

type LanguageResources = Record<Namespace, unknown>;

// English is the default and stays on the initial render path. The other
// language packs are loaded only when a user selects them. Importing all four
// packs here made the initial mobile bundle carry roughly 240 KB of translation
// data that the default page did not use.
const lazyLanguageResources: Record<Exclude<SupportedLanguage, "en">, () => Promise<LanguageResources>> = {
    hi: () => Promise.all([
        import("./languages/hi/ui_text.json"), import("./languages/hi/layout.json"),
        import("./languages/hi/auth.json"), import("./languages/hi/users.json"),
        import("./languages/hi/policies.json"), import("./languages/hi/permissions.json"),
        import("./languages/hi/authorization.json"), import("./languages/hi/audit_log.json"),
        import("./languages/hi/account_settings.json"), import("./languages/hi/dashboard.json"),
        import("./languages/hi/rate_limits.json"), import("./languages/hi/errors.json"),
    ]).then(([ui_text, layout, auth, users, policies, permissions, authorization, audit_log, account_settings, dashboard, rate_limits, errors]) => ({
        ui_text: ui_text.default, layout: layout.default, auth: auth.default, users: users.default,
        policies: policies.default, permissions: permissions.default, authorization: authorization.default,
        audit_log: audit_log.default, account_settings: account_settings.default, dashboard: dashboard.default,
        rate_limits: rate_limits.default, errors: errors.default,
    })),
    mr: () => Promise.all([
        import("./languages/mr/ui_text.json"), import("./languages/mr/layout.json"),
        import("./languages/mr/auth.json"), import("./languages/mr/users.json"),
        import("./languages/mr/policies.json"), import("./languages/mr/permissions.json"),
        import("./languages/mr/authorization.json"), import("./languages/mr/audit_log.json"),
        import("./languages/mr/account_settings.json"), import("./languages/mr/dashboard.json"),
        import("./languages/mr/rate_limits.json"), import("./languages/mr/errors.json"),
    ]).then(([ui_text, layout, auth, users, policies, permissions, authorization, audit_log, account_settings, dashboard, rate_limits, errors]) => ({
        ui_text: ui_text.default, layout: layout.default, auth: auth.default, users: users.default,
        policies: policies.default, permissions: permissions.default, authorization: authorization.default,
        audit_log: audit_log.default, account_settings: account_settings.default, dashboard: dashboard.default,
        rate_limits: rate_limits.default, errors: errors.default,
    })),
    gu: () => Promise.all([
        import("./languages/gu/ui_text.json"), import("./languages/gu/layout.json"),
        import("./languages/gu/auth.json"), import("./languages/gu/users.json"),
        import("./languages/gu/policies.json"), import("./languages/gu/permissions.json"),
        import("./languages/gu/authorization.json"), import("./languages/gu/audit_log.json"),
        import("./languages/gu/account_settings.json"), import("./languages/gu/dashboard.json"),
        import("./languages/gu/rate_limits.json"), import("./languages/gu/errors.json"),
    ]).then(([ui_text, layout, auth, users, policies, permissions, authorization, audit_log, account_settings, dashboard, rate_limits, errors]) => ({
        ui_text: ui_text.default, layout: layout.default, auth: auth.default, users: users.default,
        policies: policies.default, permissions: permissions.default, authorization: authorization.default,
        audit_log: audit_log.default, account_settings: account_settings.default, dashboard: dashboard.default,
        rate_limits: rate_limits.default, errors: errors.default,
    })),
};

translations.use(initReactI18next).init({
    resources: {
        en: {
            ui_text: enUiText,
            layout: enLayout,
            auth: enAuth,
            users: enUsers,
            policies: enPolicies,
            permissions: enPermissions,
            authorization: enAuthorization,
            audit_log: enAuditLog,
            account_settings: enAccountSettings,
            dashboard: enDashboard,
            rate_limits: enRateLimits,
            errors: enErrors,
        },
    },
    lng: "en",
    fallbackLng: "en",
    // i18next mutates options.ns in place when a downstream app registers a new
    // namespace via addResourceBundle. Pass a copy so that mutation can't leak
    // back into our exported NAMESPACES const.
    ns: [...NAMESPACES],
    defaultNS: "ui_text",
    interpolation: {
        escapeValue: false,
    },
});

const loadedLanguages = new Set<SupportedLanguage>(["en"]);

export async function loadLanguage(language: SupportedLanguage): Promise<void> {
    if (loadedLanguages.has(language)) return;
    if (language === "en") return;
    const resources = await lazyLanguageResources[language]();
    for (const namespace of NAMESPACES) {
        translations.addResourceBundle(language, namespace, resources[namespace], true, true);
    }
    loadedLanguages.add(language);
}

export default translations;
