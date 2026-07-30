/**
 * Single source of truth for the product name shown in the UI (navbar,
 * auth pages, document title); change it here once rather than hunting
 * down every hardcoded occurrence.
 */
export const APP_NAME = import.meta.env.VITE_APP_NAME;

const settings = {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
};

export default settings;