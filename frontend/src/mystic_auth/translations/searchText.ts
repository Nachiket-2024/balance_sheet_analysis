import translations from "./translations";
import type { Namespace } from "./translations";

function flattenValues(node: unknown, out: string[]): void {
    if (typeof node === "string") {
        out.push(node);
    } else if (node && typeof node === "object") {
        for (const value of Object.values(node)) flattenValues(value, out);
    }
}

function getPath(obj: unknown, path: string): unknown {
    return path
        .split(".")
        .reduce<unknown>((acc, key) => (acc && typeof acc === "object" ? (acc as Record<string, unknown>)[key] : undefined), obj);
}

/**
 * Every leaf string in a translation namespace, in the given language,
 * space-joined and lowercased: the full visible text of a whole page.
 * CommandPalette's content search uses this so any word visible on a page
 * (a column header, a filter label, a toast message) can surface it as a
 * result, without hand-maintaining a keyword list that would drift from the
 * page's actual copy.
 */
export function namespaceSearchText(namespace: Namespace, language: string): string {
    const bundle = translations.getResourceBundle(language, namespace) as unknown;
    const values: string[] = [];
    flattenValues(bundle, values);
    return values.join(" ").toLowerCase();
}

/**
 * Same idea as `namespaceSearchText`, but scoped to one or more dot-paths
 * within the namespace (e.g. `"changePassword"`, `"tabs.password"`) rather
 * than the whole file. Used for a SearchItem that should only match the
 * tab/section it navigates to, not every string in a namespace shared by
 * several tabs (account_settings.json, audit_log.json).
 */
export function scopedSearchText(namespace: Namespace, language: string, paths: string[]): string {
    const bundle = translations.getResourceBundle(language, namespace) as unknown;
    const values: string[] = [];
    for (const path of paths) flattenValues(getPath(bundle, path), values);
    return values.join(" ").toLowerCase();
}

function collectMatches(node: unknown, lowerQuery: string, out: Set<string>): void {
    if (typeof node === "string") {
        // Skip strings with unresolved `{{placeholder}}` tokens: we don't have
        // the interpolation values here, and showing the raw template (e.g.
        // "Policies for {{email}}") as a result is worse than not surfacing
        // it at all.
        if (node.toLowerCase().includes(lowerQuery) && !node.includes("{{")) out.add(node);
    } else if (node && typeof node === "object") {
        for (const value of Object.values(node)) collectMatches(value, lowerQuery, out);
    }
}

/**
 * Every distinct leaf string in a translation namespace that itself contains
 * `query` (case-insensitive), in original casing: the "Ctrl+F on this page"
 * building block for CommandPalette's per-string match results, as opposed
 * to `namespaceSearchText`'s single blob used only to decide whether the
 * page matches at all.
 */
export function namespaceMatches(namespace: Namespace, language: string, query: string): string[] {
    const bundle = translations.getResourceBundle(language, namespace) as unknown;
    const out = new Set<string>();
    collectMatches(bundle, query.toLowerCase(), out);
    return [...out];
}

/** Same idea as `namespaceMatches`, scoped to one or more dot-paths: the
 * per-string counterpart to `scopedSearchText`. */
export function scopedMatches(namespace: Namespace, language: string, paths: string[], query: string): string[] {
    const bundle = translations.getResourceBundle(language, namespace) as unknown;
    const out = new Set<string>();
    const lowerQuery = query.toLowerCase();
    for (const path of paths) collectMatches(getPath(bundle, path), lowerQuery, out);
    return [...out];
}
