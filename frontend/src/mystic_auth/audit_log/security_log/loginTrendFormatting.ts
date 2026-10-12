import type { SupportedLanguage } from "../../translations/translations";
import { formatNumber } from "../../translations/numerals";
import { monthNameShort } from "../../translations/monthNames";

export function formatDayLabel(iso: string, language: SupportedLanguage): string {
    const date = new Date(`${iso}T00:00:00`);
    return formatNumber(`${date.getDate()} ${monthNameShort(date.getMonth(), language)}`, language);
}

export const formatAxisLabel = formatDayLabel;

export function niceMax(value: number): number {
    if (value <= 1) return 2;
    if (value <= 5) return value;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const residual = value / magnitude;
    const niceResidual = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 2.5 ? 2.5 : residual <= 5 ? 5 : 10;
    return niceResidual * magnitude;
}
