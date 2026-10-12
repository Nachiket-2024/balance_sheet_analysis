import React, { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { BarChart3, Table2 } from "lucide-react";

import { Skeleton } from "../../ui/shadcn/skeleton";
import FormAlert from "../../ui/feedback/FormAlert";
import AppTooltip from "../../ui/feedback/AppTooltip";
import SegmentedControl from "../../ui/filters/SegmentedControl";
import { cn } from "../../ui/styles/classNames";
import type { LoginTrendPoint } from "../../api/audit_api";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";
import LoginTrendTable from "./LoginTrendTable";
import { formatAxisLabel, formatDayLabel, niceMax } from "./loginTrendFormatting";

interface LoginTrendChartProps {
    data: LoginTrendPoint[] | undefined;
    isLoading: boolean;
    isFetching?: boolean;
    isError: boolean;
    errorMessage?: string;
}

// CHART_HEIGHT is kept as a plain constant (not a CSS var) so the SVG's own
// height={} prop stays in sync automatically; Tailwind can't read a JS
// constant into an arbitrary-value class, so `h-[130px]`/`h-[200px]` and the
// Y-axis column's `w-[44px]` literals below must be changed by hand with it
// (a strict hash-only CSP forbids a dynamic/computed inline style here).
// 44px fits a 5-digit, thousands-separated tick ("12,500") without wrapping
// across every language's own separator (see numerals.ts).
const CHART_HEIGHT = 130;
const BAR_WIDTH_RATIO = 0.55;


/**
 * LoginTrendChart
 * ----------------------------
 * Daily sign-in success/failure counts as a stacked bar chart, so a spike (a brute-force run, a
 * lockout wave) is visible at a glance instead of requiring paging through rows below. Gray for
 * success, red for failure rather than green/red: green and red aren't distinguishable enough
 * for deutan colorblindness, and failures are the thing this chart exists to surface. The chart
 * follows the page's selected time range and has no controls of its own: a trend glance, not a
 * second filterable table.
 *
 * Every bar is labeled with its day-of-month, not just the first/last, so a reader can tell
 * which day a spike happened on. Hovering or keyboard-focusing a bar lifts it slightly and
 * opens a tooltip with the full date and exact counts; all of this is already reachable in
 * the security-log table below, so the chart is a glance-level enhancement, not a data source.
 */
const LoginTrendChart: React.FC<LoginTrendChartProps> = ({ data, isLoading, isFetching = false, isError, errorMessage }) => {
    const { t } = useTranslation(["audit_log", "ui_text"]);
    // chromeLanguage, not pageLanguage, for every number/date here: see
    // AllAuthorizationLogSection.tsx's matching comment. Numerals stay ASCII even in a mixed
    // "en+hi" mode; only the translated labels (t()) switch with pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const [hovered, setHovered] = useState<number | null>(null);
    // "All attempts / Failed only" - rescales the bars against failures alone so a normal day's
    // handful of failures stays readable next to a spike, instead of being squashed flat by the
    // successes stacked on top of it. "Chart / Table" swaps the whole plot for a plain table, so
    // no value here depends on hovering a bar's tooltip. Local, session-only state (not the
    // uiStore): a glance-level display preference, not a filter that should survive a tab switch.
    const [chartMode, setChartMode] = useState<"all" | "failed">("all");
    const [chartView, setChartView] = useState<"chart" | "table">("chart");

    // The hovered-day tooltip's horizontal position is genuinely dynamic
    // (depends on which bar is hovered and how many days are plotted), so
    // it can't be a static Tailwind class the way the chart's other inline
    // styles were converted to (see the comment above CHART_HEIGHT).
    // Setting it via the CSSOM (element.style.setProperty)
    // rather than React's `style` prop keeps it out of the `style=""` HTML
    // attribute entirely, so a strict hash-only CSP's style-src never sees
    // it and never flags it - CSP only governs markup/attribute-driven
    // styles and <style> elements, not direct DOM property assignment.
    const tooltipRef = useRef<HTMLDivElement>(null);
    useLayoutEffect(() => {
        if (!tooltipRef.current || hovered === null || !data || data.length === 0) return;
        const dw = 100 / data.length;
        tooltipRef.current.style.setProperty("--tooltip-left", `${hovered * dw + dw / 2}%`);
    }, [hovered, data]);

    if (isLoading) return <Skeleton className="h-[200px]" />;
    if (isError) return <FormAlert status="error">{errorMessage ?? t("security.failedToLoadTrend")}</FormAlert>;
    if (!data || data.length === 0) return <p className="text-sm text-fg-muted">{t("security.emptyTrend")}</p>;

    const rawMax =
        chartMode === "failed"
            ? Math.max(1, ...data.map((d) => d.failure))
            : Math.max(1, ...data.map((d) => d.success + d.failure));
    const scaleMax = niceMax(rawMax);
    const dayWidth = 100 / data.length;
    const barWidth = dayWidth * BAR_WIDTH_RATIO;
    const totalSuccess = data.reduce((sum, d) => sum + d.success, 0);
    const totalFailure = data.reduce((sum, d) => sum + d.failure, 0);
    const totalAttempts = totalSuccess + totalFailure;
    const failureRate = totalAttempts === 0 ? 0 : Math.round((totalFailure / totalAttempts) * 100);
    // The single worst day by failure count, so a reader can jump straight to the day behind
    // a spike instead of scanning every bar. Ties keep the earliest day (reduce's `>`, not
    // `>=`), an arbitrary but stable tiebreak.
    const worstDay = data.reduce((worst, d) => (d.failure > worst.failure ? d : worst), data[0]);
    const plotHeight = CHART_HEIGHT - 12;
    const hoveredPoint = hovered !== null ? data[hovered] : null;
    // Every label at 14 days is already tight; at 30/90 it overlaps outright, so only every
    // Nth tick renders once the range grows past what fits legibly.
    const labelStride = data.length > 60 ? 7 : data.length > 30 ? 3 : data.length > 14 ? 2 : 1;

    const toggles = (
        <div className="flex items-center gap-2 flex-wrap">
            <SegmentedControl
                ariaLabel={t("security.chartToggle.barsShowAriaLabel")}
                value={chartMode}
                onChange={(v) => setChartMode(v as "all" | "failed")}
                options={[
                    { value: "all", label: t("security.chartToggle.allAttempts") },
                    { value: "failed", label: t("security.chartToggle.failedOnly") },
                ]}
            />
            <SegmentedControl
                ariaLabel={t("security.chartToggle.viewAriaLabel")}
                value={chartView}
                onChange={(v) => setChartView(v as "chart" | "table")}
                options={[
                    {
                        value: "chart",
                        label: (
                            <AppTooltip content={t("security.chartToggle.chartView")}>
                                <BarChart3 size={14} aria-label={t("security.chartToggle.chartView")} />
                            </AppTooltip>
                        ),
                    },
                    {
                        value: "table",
                        label: (
                            <AppTooltip content={t("security.chartToggle.tableView")}>
                                <Table2 size={14} aria-label={t("security.chartToggle.tableView")} />
                            </AppTooltip>
                        ),
                    },
                ]}
            />
        </div>
    );

    if (chartView === "table") {
        return <LoginTrendTable data={data} language={language} toggles={toggles} />;
    }

    return (
        <div className="relative">
            {isFetching && (
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden bg-[var(--brand-tint)]" role="status" aria-label={t("ui_text:loading")}>
                    <div className="h-full w-1/3 bg-brand-solid animate-[data-table-progress_1.1s_ease-in-out_infinite]" />
                </div>
            )}
            <div className="flex items-start gap-6 flex-wrap mb-3">
                <div className="flex items-center gap-5 flex-wrap">
                    <div className="text-center">
                        <p className="text-2xl font-bold leading-none">{formatNumber(totalAttempts, language)}</p>
                        <p className="text-xs text-fg-muted mt-1 whitespace-nowrap">{t("security.kpi.attempts")}</p>
                    </div>
                    <div className="text-center">
                        <p className="text-2xl font-bold leading-none text-red-fg">{formatNumber(totalFailure, language)}</p>
                        <p className="text-xs text-fg-muted mt-1 whitespace-nowrap">{t("security.kpi.failed")}</p>
                    </div>
                    <div className="text-center">
                        <p className="text-2xl font-bold leading-none">{formatNumber(failureRate, language)}%</p>
                        <p className="text-xs text-fg-muted mt-1 whitespace-nowrap">{t("security.kpi.failureRate")}</p>
                    </div>
                    {worstDay.failure > 0 && (
                        <div className="text-center">
                            <p className="text-2xl font-bold leading-none">{formatDayLabel(worstDay.date, language)}</p>
                            <p className="text-xs text-fg-muted mt-1 whitespace-nowrap">
                                {t("security.kpi.mostFailures", { count: formatNumber(worstDay.failure, language) })}
                            </p>
                        </div>
                    )}
                </div>

                <div className="flex flex-col gap-1 ml-auto items-end">
                    <div className="flex items-center gap-5 flex-wrap">
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-sm bg-[var(--green-500)]" />
                            <p className="text-sm text-fg-muted">{t("security.successCount", { count: formatNumber(totalSuccess, language) })}</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-sm bg-[var(--red-500)]" />
                            <p className="text-sm text-fg-muted">{t("security.failedCount", { count: formatNumber(totalFailure, language) })}</p>
                        </div>
                    </div>
                    <p className="text-xs text-fg-muted">
                        {t("security.trendRange", {
                            from: formatDayLabel(data[0].date, language),
                            to: formatDayLabel(data[data.length - 1].date, language),
                        })}
                    </p>
                    {toggles}
                </div>
            </div>

            <div className="flex items-stretch gap-2">
                {/* Y-axis: 0 / half / max, evenly spaced against the same
                    plotHeight the bars themselves scale against. */}
                <div
                    className="flex flex-col justify-between shrink-0 pb-3 h-[130px] w-[44px]"
                    data-testid="chart-y-axis"
                >
                    <p className="text-xs text-fg-muted text-right">{formatNumber(scaleMax, language)}</p>
                    <p className="text-xs text-fg-muted text-right">{formatNumber(Math.round(scaleMax / 2), language)}</p>
                    <p className="text-xs text-fg-muted text-right">{formatNumber(0, language)}</p>
                </div>

                <div className="flex-1 min-w-0 relative">
                    {hoveredPoint && (
                        <div
                            ref={tooltipRef}
                            className="absolute top-0 left-(--tooltip-left) -translate-x-1/2 -translate-y-full bg-bg-surface border border-border-default rounded-md shadow-md px-3 py-2 z-10 pointer-events-none whitespace-nowrap"
                        >
                            <p className="text-sm font-semibold mb-1">
                                {formatDayLabel(hoveredPoint.date, language)}
                            </p>
                            <div className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-xs bg-[var(--green-500)]" />
                                <p className="text-xs text-fg-muted">{t("security.successLabel")}</p>
                                <p className="text-xs font-semibold">{formatNumber(hoveredPoint.success, language)}</p>
                            </div>
                            <div className="flex items-center gap-1.5">
                                <div className="w-2 h-2 rounded-xs bg-[var(--red-500)]" />
                                <p className="text-xs text-fg-muted">{t("security.failedLabel")}</p>
                                <p className="text-xs font-semibold">{formatNumber(hoveredPoint.failure, language)}</p>
                            </div>
                        </div>
                    )}

                    <svg
                        width="100%"
                        height={CHART_HEIGHT}
                        role="img"
                        aria-label={t("security.chartAriaLabel", {
                            from: formatDayLabel(data[0].date, language),
                            to: formatDayLabel(data[data.length - 1].date, language),
                            success: formatNumber(totalSuccess, language),
                            failure: formatNumber(totalFailure, language),
                        })}
                    >
                        {/* Gridlines at half/max, hairline and recessive. */}
                        {[0.5, 1].map((fraction) => (
                            <line
                                key={fraction}
                                x1="0"
                                y1={CHART_HEIGHT - fraction * plotHeight - 0.5}
                                x2="100%"
                                y2={CHART_HEIGHT - fraction * plotHeight - 0.5}
                                stroke="var(--border-default)"
                                strokeWidth="1"
                            />
                        ))}
                        {/* X axis and Y axis, solid and one step more visible than the gridlines above. */}
                        <line
                            x1="0" y1={CHART_HEIGHT - 0.5} x2="100%" y2={CHART_HEIGHT - 0.5}
                            stroke="var(--fg-muted)" strokeWidth="1"
                        />
                        <line
                            x1="0.5" y1="0" x2="0.5" y2={CHART_HEIGHT}
                            stroke="var(--fg-muted)" strokeWidth="1"
                        />
                        {data.map((point, i) => {
                            const total = point.success + point.failure;
                            // Failed-only rescales against failures alone: the bar IS the
                            // failure count, no success segment stacked on top of it.
                            const barHeight =
                                chartMode === "failed"
                                    ? (point.failure / scaleMax) * plotHeight
                                    : (total / scaleMax) * plotHeight;
                            const failureHeight =
                                chartMode === "failed" ? barHeight : total === 0 ? 0 : (point.failure / total) * barHeight;
                            const successHeight = chartMode === "failed" ? 0 : barHeight - failureHeight;
                            // Capped so a handful of days (a 90-day range) don't blow up into
                            // slabs wider than a bar chart should read. `calc()` mixes the day
                            // column's % with a fixed px cap; modern browsers resolve each unit
                            // against its own reference and sum them, so this centers correctly
                            // whether or not the cap is actually binding.
                            const cappedWidth = `min(${barWidth}%, 24px)`;
                            const x = `calc(${i * dayWidth}% + (${dayWidth}% - ${cappedWidth}) / 2)`;
                            const isHovered = hovered === i;

                            return (
                                <g
                                    key={point.date}
                                    tabIndex={0}
                                    className="outline-none cursor-pointer"
                                    onMouseEnter={() => setHovered(i)}
                                    onMouseLeave={() => setHovered(null)}
                                    onFocus={() => setHovered(i)}
                                    onBlur={() => setHovered(null)}
                                >
                                    {/* Wider transparent hit area than the bar itself, so a thin/zero-height bar is still hoverable/focusable. */}
                                    <rect x={`${i * dayWidth}%`} y={0} width={`${dayWidth}%`} height={CHART_HEIGHT} fill="transparent" />
                                    {successHeight > 0 && (
                                        <rect
                                            x={x}
                                            y={CHART_HEIGHT - barHeight}
                                            width={cappedWidth}
                                            height={successHeight}
                                            rx={2}
                                            fill="var(--green-500)"
                                            opacity={isHovered ? 1 : 0.9}
                                        />
                                    )}
                                    {failureHeight > 0 && (
                                        <rect
                                            x={x}
                                            y={CHART_HEIGHT - failureHeight}
                                            width={cappedWidth}
                                            height={failureHeight}
                                            rx={2}
                                            fill="var(--red-500)"
                                            opacity={isHovered ? 1 : 0.9}
                                        />
                                    )}
                                </g>
                            );
                        })}
                    </svg>

                    <div className="flex items-center mt-1">
                        {data.map((point, i) => (
                            // Every column is dayWidth=100/data.length wide - all equal - so
                            // flex-1 gets the identical even split without a computed inline
                            // style (a strict hash-only CSP can't allow one).
                            <div key={point.date} className="flex-1 text-center">
                                <p
                                    className={cn(
                                        "text-xs whitespace-nowrap",
                                        hovered === i ? "text-fg-default font-semibold" : "text-fg-muted font-normal"
                                    )}
                                >
                                    {/* Thinned at 30/90 days (labelStride) - every tick still gets
                                        a hover/focus tooltip via the bar above it, so nothing is
                                        actually lost by skipping its printed label. */}
                                    {(i % labelStride === 0 || hovered === i) && formatAxisLabel(point.date, language)}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoginTrendChart;
