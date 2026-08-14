import type { SupportedLanguage } from "./translations";

/**
 * ASCII-digit -> native-numeral lookup per supported language, keyed the
 * same way translations/languages/*\/*.json are: one entry per
 * SupportedLanguage, so adding a language here and a language folder are the
 * same-shaped change. `null` means "render digits as-is" (English).
 *
 * Hindi and Marathi both use the Devanagari script's digits (same glyphs,
 * ०-९), but are kept as two separate entries rather than one shared
 * constant so a future language that diverges doesn't require restructuring
 * this map. Gujarati has its own distinct glyph set (૦-૯).
 */
const DEVANAGARI_DIGITS: Record<string, string> = {
    "0": "०", "1": "१", "2": "२", "3": "३", "4": "४",
    "5": "५", "6": "६", "7": "७", "8": "८", "9": "९",
};

const GUJARATI_DIGITS: Record<string, string> = {
    "0": "૦", "1": "૧", "2": "૨", "3": "૩", "4": "૪",
    "5": "૫", "6": "૬", "7": "૭", "8": "૮", "9": "૯",
};

const DIGIT_MAPS: Record<SupportedLanguage, Record<string, string> | null> = {
    en: null,
    hi: DEVANAGARI_DIGITS,
    mr: DEVANAGARI_DIGITS,
    gu: GUJARATI_DIGITS,
};

/**
 * Renders a number using the given language's native numerals (e.g. 128 ->
 * "१२८" for hi/mr), falling back to plain ASCII digits for English or any
 * value that isn't a finite number. Used anywhere a raw count/index is
 * displayed (stat tiles, pagination, table row numbers) so those stay in
 * step with the language toggle the same way translated text does.
 */
export function formatNumber(value: number | string | undefined, language: SupportedLanguage): string {
    if (value === undefined) return "-";
    const str = String(value);
    const map = DIGIT_MAPS[language];
    if (!map) return str;
    return str.replace(/[0-9]/g, (digit) => map[digit]);
}
