import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Box, HStack, Text } from "@chakra-ui/react";

import { Card } from "../sdk";
import type { BalanceSheet } from "../api/balance_sheet_api";

interface BalanceSheetChartProps {
    balanceSheets: BalanceSheet[];
}

const SERIES: { key: string; label: string; color: string }[] = [
    { key: "total_assets", label: "Total assets", color: "#2563eb" },
    { key: "total_liabilities_net_minority_interest", label: "Total liabilities", color: "#dc2626" },
    { key: "stockholders_equity", label: "Stockholders' equity", color: "#16a34a" },
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
        <Card p={5} mb={6}>
            <Text fontWeight="semibold" mb={4} fontSize="lg">
                Assets, liabilities & equity over time
            </Text>

            {/* Axis titles are plain Chakra text outside the chart's own SVG,
                not recharts' inline <Label> (which sits inside the plot area
                and, depending on offset direction, can overlap the tick
                numbers it's meant to caption). Laying them out with flexbox
                keeps a fixed gap from the tick labels regardless of chart
                size, so they can never collide. */}
            <HStack align="stretch" gap={1}>
                <Box flexShrink={0} w="28px" display="flex" alignItems="center" justifyContent="center">
                    <Text
                        fontSize="md"
                        fontWeight="semibold"
                        color="fg.muted"
                        whiteSpace="nowrap"
                        style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
                    >
                        Amount (USD)
                    </Text>
                </Box>

                <Box flex="1" minW={0}>
                    {/* initialDimension is the size used until ResizeObserver reports a
                        real measurement; real browsers always have ResizeObserver, so
                        this only affects the very first paint frame there, but it's
                        also what makes this chart testable in jsdom at all, which has
                        no ResizeObserver and would otherwise measure a permanent 0x0
                        container and render no children (see BalanceSheetChart.test.tsx). */}
                    <ResponsiveContainer width="100%" height={340} initialDimension={{ width: 800, height: 340 }}>
                        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--chakra-colors-border-default)" />
                            <XAxis
                                dataKey="year"
                                stroke="var(--chakra-colors-fg-muted)"
                                tick={{ fill: "var(--chakra-colors-fg-muted)", fontSize: 12 }}
                                tickMargin={8}
                            />
                            <YAxis
                                tickFormatter={formatCompactUsd}
                                width={64}
                                stroke="var(--chakra-colors-fg-muted)"
                                tick={{ fill: "var(--chakra-colors-fg-muted)", fontSize: 12 }}
                                tickMargin={6}
                            />
                            {/* Recharts v3 infers a wider Tooltip formatter type than v2. */}
                            <Tooltip
                                formatter={(value) => (typeof value === "number" ? value.toLocaleString() : value)}
                                labelFormatter={(label) => `Fiscal year ${label}`}
                                contentStyle={{
                                    background: "var(--chakra-colors-bg-surface)",
                                    border: "1px solid var(--chakra-colors-border-default)",
                                    borderRadius: "6px",
                                    color: "var(--chakra-colors-fg-default)",
                                }}
                                labelStyle={{ color: "var(--chakra-colors-fg-default)", fontWeight: 600 }}
                            />
                            <Legend wrapperStyle={{ color: "var(--chakra-colors-fg-muted)", paddingTop: 8 }} />
                            {SERIES.map((series) => (
                                <Line
                                    key={series.key}
                                    type="monotone"
                                    dataKey={series.key}
                                    name={series.label}
                                    stroke={series.color}
                                    strokeWidth={2}
                                    dot={{ r: 3 }}
                                    activeDot={{ r: 5 }}
                                    connectNulls
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>

                    <Text fontSize="md" fontWeight="semibold" color="fg.muted" textAlign="center" mt={1}>
                        Fiscal year
                    </Text>
                </Box>
            </HStack>
        </Card>
    );
};

export default BalanceSheetChart;
