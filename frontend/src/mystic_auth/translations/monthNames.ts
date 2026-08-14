import type { SupportedLanguage } from "./translations";

/**
 * Short month names per supported language (index 0 = January), used
 * wherever a date renders as "dd Mon yyyy" rather than via toLocaleDateString
 * (which can't be told to keep day-before-month while still swapping the
 * month name itself per language). Keyed the same way numerals.ts's
 * DIGIT_MAPS is: one entry per SupportedLanguage.
 */
const MONTH_NAMES_SHORT: Record<SupportedLanguage, readonly string[]> = {
    en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    hi: ["जन", "फ़र", "मार्च", "अप्रैल", "मई", "जून", "जुल", "अग", "सित", "अक्तू", "नव", "दिस"],
    mr: ["जाने", "फेब्रु", "मार्च", "एप्रि", "मे", "जून", "जुलै", "ऑग", "सप्टें", "ऑक्टो", "नोव्हें", "डिसें"],
    gu: ["જાન", "ફેબ", "માર્ચ", "એપ્રિ", "મે", "જૂન", "જુલા", "ઑગ", "સપ્ટે", "ઑક્ટો", "નવે", "ડિસે"],
};

/** `date.getMonth()` (0-11) -> that language's short month name. */
export function monthNameShort(monthIndex: number, language: SupportedLanguage): string {
    return MONTH_NAMES_SHORT[language][monthIndex];
}
