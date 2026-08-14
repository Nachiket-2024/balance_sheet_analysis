import translations from "i18next";
import { initReactI18next } from "react-i18next";

import enUiText from "./languages/en/ui_text.json";
import enLayout from "./languages/en/layout.json";
import enAuth from "./languages/en/auth.json";
import enUsers from "./languages/en/users.json";
import enPolicies from "./languages/en/policies.json";
import enAuthorization from "./languages/en/authorization.json";
import enAuditLog from "./languages/en/audit_log.json";
import enAccountSettings from "./languages/en/account_settings.json";
import enDashboard from "./languages/en/dashboard.json";
import enStatusPages from "./languages/en/status_pages.json";
import enErrors from "./languages/en/errors.json";

import hiUiText from "./languages/hi/ui_text.json";
import hiLayout from "./languages/hi/layout.json";
import hiAuth from "./languages/hi/auth.json";
import hiUsers from "./languages/hi/users.json";
import hiPolicies from "./languages/hi/policies.json";
import hiAuthorization from "./languages/hi/authorization.json";
import hiAuditLog from "./languages/hi/audit_log.json";
import hiAccountSettings from "./languages/hi/account_settings.json";
import hiDashboard from "./languages/hi/dashboard.json";
import hiStatusPages from "./languages/hi/status_pages.json";
import hiErrors from "./languages/hi/errors.json";

import mrUiText from "./languages/mr/ui_text.json";
import mrLayout from "./languages/mr/layout.json";
import mrAuth from "./languages/mr/auth.json";
import mrUsers from "./languages/mr/users.json";
import mrPolicies from "./languages/mr/policies.json";
import mrAuthorization from "./languages/mr/authorization.json";
import mrAuditLog from "./languages/mr/audit_log.json";
import mrAccountSettings from "./languages/mr/account_settings.json";
import mrDashboard from "./languages/mr/dashboard.json";
import mrStatusPages from "./languages/mr/status_pages.json";
import mrErrors from "./languages/mr/errors.json";

import guUiText from "./languages/gu/ui_text.json";
import guLayout from "./languages/gu/layout.json";
import guAuth from "./languages/gu/auth.json";
import guUsers from "./languages/gu/users.json";
import guPolicies from "./languages/gu/policies.json";
import guAuthorization from "./languages/gu/authorization.json";
import guAuditLog from "./languages/gu/audit_log.json";
import guAccountSettings from "./languages/gu/account_settings.json";
import guDashboard from "./languages/gu/dashboard.json";
import guStatusPages from "./languages/gu/status_pages.json";
import guErrors from "./languages/gu/errors.json";

// One namespace per feature folder under src/mystic_auth/, so translation
// files stay small and map 1:1 to code ownership rather than one giant JSON.
export const NAMESPACES = [
    "ui_text",
    "layout",
    "auth",
    "users",
    "policies",
    "authorization",
    "audit_log",
    "account_settings",
    "dashboard",
    "status_pages",
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

translations.use(initReactI18next).init({
    resources: {
        en: {
            ui_text: enUiText,
            layout: enLayout,
            auth: enAuth,
            users: enUsers,
            policies: enPolicies,
            authorization: enAuthorization,
            audit_log: enAuditLog,
            account_settings: enAccountSettings,
            dashboard: enDashboard,
            status_pages: enStatusPages,
            errors: enErrors,
        },
        hi: {
            ui_text: hiUiText,
            layout: hiLayout,
            auth: hiAuth,
            users: hiUsers,
            policies: hiPolicies,
            authorization: hiAuthorization,
            audit_log: hiAuditLog,
            account_settings: hiAccountSettings,
            dashboard: hiDashboard,
            status_pages: hiStatusPages,
            errors: hiErrors,
        },
        mr: {
            ui_text: mrUiText,
            layout: mrLayout,
            auth: mrAuth,
            users: mrUsers,
            policies: mrPolicies,
            authorization: mrAuthorization,
            audit_log: mrAuditLog,
            account_settings: mrAccountSettings,
            dashboard: mrDashboard,
            status_pages: mrStatusPages,
            errors: mrErrors,
        },
        gu: {
            ui_text: guUiText,
            layout: guLayout,
            auth: guAuth,
            users: guUsers,
            policies: guPolicies,
            authorization: guAuthorization,
            audit_log: guAuditLog,
            account_settings: guAccountSettings,
            dashboard: guDashboard,
            status_pages: guStatusPages,
            errors: guErrors,
        },
    },
    lng: "en",
    fallbackLng: "en",
    ns: NAMESPACES,
    defaultNS: "ui_text",
    interpolation: {
        escapeValue: false,
    },
});

export default translations;
