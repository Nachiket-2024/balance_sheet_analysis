import React from "react";
import { useTranslation } from "react-i18next";

import type { LoginTrendPoint } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatNumber } from "../../translations/numerals";
import { formatDayLabel } from "./loginTrendFormatting";

interface LoginTrendTableProps { data: LoginTrendPoint[]; language: SupportedLanguage; toggles: React.ReactNode; }

const LoginTrendTable: React.FC<LoginTrendTableProps> = ({ data, language, toggles }) => {
    const { t } = useTranslation("audit_log");
    return <div><div className="flex items-center justify-between flex-wrap gap-3 mb-3"><p className="text-xs text-fg-muted">{t("security.trendRange", { from: formatDayLabel(data[0].date, language), to: formatDayLabel(data[data.length - 1].date, language) })}</p>{toggles}</div><div className="border border-border-default rounded-lg overflow-hidden"><table className="w-full text-sm"><thead><tr className="border-b border-border-default bg-bg-canvas"><th className="text-left font-semibold px-3 py-2">{t("security.chartTable.date")}</th><th className="text-right font-semibold px-3 py-2">{t("security.chartTable.success")}</th><th className="text-right font-semibold px-3 py-2">{t("security.chartTable.failed")}</th><th className="text-right font-semibold px-3 py-2">{t("security.chartTable.failureRate")}</th></tr></thead><tbody>{data.map((point) => { const total = point.success + point.failure; const rate = total === 0 ? 0 : Math.round((point.failure / total) * 100); return <tr key={point.date} className="border-b border-border-default last:border-b-0"><td className="px-3 py-1.5">{formatDayLabel(point.date, language)}</td><td className="text-right px-3 py-1.5">{formatNumber(point.success, language)}</td><td className="text-right px-3 py-1.5 text-red-fg">{formatNumber(point.failure, language)}</td><td className="text-right px-3 py-1.5">{formatNumber(rate, language)}%</td></tr>; })}</tbody></table></div></div>;
};

export default LoginTrendTable;
