import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LineChart as ChartIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Card } from "../sdk";
import type { BalanceSheet } from "../api/balance_sheet_api";

interface BalanceSheetChartProps {
    balanceSheets: BalanceSheet[];
}

// Keyed by translation key (not literal text, unlike upstream's own static
// label constants elsewhere) since the series' display name has to follow
// the caller's current language via useTranslation below.
const SERIES: { key: string; labelKey: string; color: string }[] = [
    { key: "total_assets", labelKey: "seriesTotalAssets", color: "#2563eb" },
    { key: "total_liabilities_net_minority_interest", labelKey: "seriesTotalLiabilities", color: "#dc2626" },
    { key: "stockholders_equity", labelKey: "seriesStockholdersEquity", color: "#16a34a" },
];

/** Compact USD ticks avoid clipped y-axis labels for large figures. */
function formatCompactUsd(value: number): string {
    const abs = Math.abs(value);
    if (abs >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `$${(value / 1e3).toFixed(1)}K`;
    return `$${value}`;
}

/**
 * Assets/liabilities/equity trend across fiscal years: problem statement
 * 1a's "plotting the sales, growth, assets, liabilities, etc." Sales/growth
 * aren't plotted (yfinance's balance-sheet endpoint has no income-statement
 * fields, see docs/app/features.md for that scope boundary); this
 * covers what the balance sheet itself actually reports.
 */
const BalanceSheetChart: React.FC<BalanceSheetChartProps> = ({ balanceSheets }) => {
    const { t } = useTranslation("balance_sheets");

    if (balanceSheets.length === 0) {
        return null;
    }

    const data = [...balanceSheets]
        .sort((a, b) => a.year - b.year)
        .map((sheet) => ({
            year: sheet.year,
            total_assets: sheet.total_assets,
            total_liabilities_net_minority_interest: sheet.total_liabilities_net_minority_interest,
            stockholders_equity: sheet.stockholders_equity,
        }));

    return (
        <Card className="mb-6 p-5">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
                <ChartIcon size={18} className="text-brand-fg" aria-hidden="true" />
                {t("chartTitle")}
            </h2>

            {/* Axis titles are plain Chakra text outside the chart's own SVG,
                not recharts' inline <Label> (which sits inside the plot area
                and, depending on offset direction, can overlap the tick
                numbers it's meant to caption). Laying them out with flexbox
                keeps a fixed gap from the tick labels regardless of chart
                size, so they can never collide. */}
            <div className="flex items-stretch gap-1">
                <div className="flex w-7 shrink-0 items-center justify-center">
                    <span className="whitespace-nowrap text-base font-semibold text-fg-muted" style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}>
                        {t("amountAxisLabel")}
                    </span>
                </div>

                <div className="min-w-0 flex-1">
                    {/* initialDimension is the size used until ResizeObserver reports a
                        real measurement; real browsers always have ResizeObserver, so
                        this only affects the very first paint frame there, but it's
                        also what makes this chart testable in jsdom at all, which has
                        no ResizeObserver and would otherwise measure a permanent 0x0
                        container and render no children (see BalanceSheetChart.test.tsx). */}
                    <ResponsiveContainer width="100%" height={280} initialDimension={{ width: 800, height: 280 }}>
                        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--border-default)" />
                            <XAxis
                                dataKey="year"
                                stroke="var(--fg-muted)"
                                tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
                                tickMargin={8}
                            />
                            <YAxis
                                tickFormatter={formatCompactUsd}
                                width={64}
                                stroke="var(--fg-muted)"
                                tick={{ fill: "var(--fg-muted)", fontSize: 12 }}
                                tickMargin={6}
                            />
                            {/* Recharts v3 infers a wider Tooltip formatter type than v2. */}
                            <Tooltip
                                formatter={(value) => (typeof value === "number" ? value.toLocaleString() : value)}
                                labelFormatter={(label) => t("tooltipFiscalYear", { year: label })}
                                contentStyle={{
                                    background: "var(--bg-surface)",
                                    border: "1px solid var(--border-default)",
                                    borderRadius: "6px",
                                    color: "var(--fg-default)",
                                }}
                                labelStyle={{ color: "var(--fg-default)", fontWeight: 600 }}
                            />
                            <Legend wrapperStyle={{ color: "var(--fg-muted)", paddingTop: 8 }} />
                            {SERIES.map((series) => (
                                <Line
                                    key={series.key}
                                    type="monotone"
                                    dataKey={series.key}
                                    name={t(series.labelKey)}
                                    stroke={series.color}
                                    strokeWidth={2}
                                    dot={{ r: 3 }}
                                    activeDot={{ r: 5 }}
                                    connectNulls
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>

                    <p className="mt-1 text-center text-base font-semibold text-fg-muted">
                        {t("fiscalYearAxisLabel")}
                    </p>
                </div>
            </div>
        </Card>
    );
};

export default BalanceSheetChart;
