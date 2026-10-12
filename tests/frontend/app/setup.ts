// App-owned counterpart to src/mystic_auth/__tests__/setup.ts's translations
// import: registers this app's own translation resources (companies/
// balance_sheets/analysis/llm namespaces, plus this app's error codes) into the same
// i18next instance before any test renders a component that calls
// useTranslation("companies" | "balance_sheets" | "analysis" | "llm"). Listed separately
// in vitest.config.ts's setupFiles rather than added to the upstream-owned
// setup.ts above.
import "@app/translations/translations";
