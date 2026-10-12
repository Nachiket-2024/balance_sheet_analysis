import type { SupportedLanguage } from "./translations";
import { formatNumber } from "./numerals";

/**
 * Hour:minute formatting per language. English keeps the familiar "8:58 PM"
 * (AM/PM, time-then-period). Hindi, Marathi, and Gujarati don't use "AM"/"PM"
 * in natural usage: CLDR day-period data instead splits the day into four
 * native words (सुबह/सकाळ/સવારે morning, दोपहर/दुपार/બપોરે afternoon,
 * शाम/संध्याकाळ/સાંજે evening, रात/रात्र/રાત્રે night) placed *before* the
 * time, e.g. "सुबह 9:30". A literal "AM"/"PM" transliteration would read as
 * wrong to a native speaker. Digits are run through formatNumber afterward
 * regardless of what Intl produced (idempotent for mr, converts hi's and
 * gu's Latin-digit defaults to native digits per numerals.ts's DIGIT_MAPS)
 * so callers get one consistent digit style.
 */
const LOCALE_TAGS: Record<SupportedLanguage, string> = {
    en: "en-US",
    hi: "hi-IN",
    mr: "mr-IN",
    gu: "gu-IN",
};

export function formatHourMinute(date: Date, language: SupportedLanguage): string {
    const formatted = language === "en"
        ? date.toLocaleTimeString(LOCALE_TAGS.en, { hour: "numeric", minute: "2-digit", hour12: true })
        : new Intl.DateTimeFormat(LOCALE_TAGS[language], { hour: "numeric", minute: "2-digit", dayPeriod: "short" }).format(date);
    return formatNumber(formatted, language);
}
