import React from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Text } from "@chakra-ui/react";

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
            <Text fontWeight="semibold" mb={4}>
                Assets, liabilities & equity over time
            </Text>
            {/* initialDimension is the size used until ResizeObserver reports a
                real measurement; real browsers always have ResizeObserver, so
                this only affects the very first paint frame there, but it's
                also what makes this chart testable in jsdom at all, which has
                no ResizeObserver and would otherwise measure a permanent 0x0
                container and render no children (see BalanceSheetChart.test.tsx). */}
            <ResponsiveContainer width="100%" height={320} initialDimension={{ width: 800, height: 320 }}>
                <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" />
                    <YAxis tickFormatter={(value: number) => value.toLocaleString()} width={90} />
                    {/* No explicit parameter type: recharts v3's Tooltip formatter type
                        is `ValueType | undefined` (ValueType itself a union including
                        string/array, not just number), narrower than the `number` this
                        was typed as under recharts v2, caught by `tsc -b`'s stricter
                        project-reference build (not the split --noEmit invocations
                        `npm run typecheck` uses). */}
                    <Tooltip formatter={(value) => (typeof value === "number" ? value.toLocaleString() : value)} />
                    <Legend />
                    {SERIES.map((series) => (
                        <Line
                            key={series.key}
                            type="monotone"
                            dataKey={series.key}
                            name={series.label}
                            stroke={series.color}
                            connectNulls
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </Card>
    );
};

export default BalanceSheetChart;
