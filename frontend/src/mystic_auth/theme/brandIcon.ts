/**
 * Same badge shape as public/favicon.svg, parameterized by fill color. This
 * is the one place "brand color -> logo/favicon color" is generated, so the
 * browser tab icon (applyFaviconAndMetaColor.ts) and the in-app logo badge
 * (Logo.tsx) stay in sync.
 */
export function getBrandIconDataUri(hex: string): string {
    const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none">` +
        `<rect width="24" height="24" rx="5" fill="${hex}"/>` +
        `<g stroke="white" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none">` +
        `<path d="M7 19V11a5 5 0 0 1 10 0v8"/>` +
        `<path d="M12 19V6"/>` +
        `<path d="M6 19h12"/>` +
        `</g>` +
        `<circle cx="10.5" cy="14" r=".55" fill="white"/>` +
        `<circle cx="13.5" cy="14" r=".55" fill="white"/>` +
        `</svg>`;
    return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
