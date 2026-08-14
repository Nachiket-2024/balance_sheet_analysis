import React, { useState } from "react";
import { Box, HStack, Skeleton, Stack, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import FormAlert from "../../ui/FormAlert";
import type { LoginTrendPoint } from "../../api/audit_api";
import { useLanguageStore } from "../../store/languageStore";
import type { SupportedLanguage } from "../../translations/translations";
import { formatNumber } from "../../translations/numerals";
import { monthNameShort } from "../../translations/monthNames";

interface LoginTrendChartProps {
    data: LoginTrendPoint[] | undefined;
    isLoading: boolean;
    isError: boolean;
}

const CHART_HEIGHT = 130;
const BAR_WIDTH_RATIO = 0.55;
const Y_AXIS_WIDTH = 28;

function formatDayLabel(iso: string, language: SupportedLanguage): string {
    const d = new Date(`${iso}T00:00:00`);
    return formatNumber(`${d.getDate()} ${monthNameShort(d.getMonth(), language)}`, language);
}

/** "21 Jul" - day-then-month so every axis tick is self-contained (no
 * separate "which month is this?" lookup against the subtitle range). */
function formatAxisLabel(iso: string, language: SupportedLanguage): string {
    const d = new Date(`${iso}T00:00:00`);
    return formatNumber(`${d.getDate()} ${monthNameShort(d.getMonth(), language)}`, language);
}

/** Rounds a max value up to a "clean" tick value (1/2/2.5/5/10 x a power of
 * ten), e.g. 432 -> 500, 7 -> 10, 21 -> 25 - so the y-axis reads 0/half/max
 * in round numbers close to the actual data, rather than an arbitrary
 * data-derived value. The 2.5 step matters: without it, a max of 21 rounds
 * all the way to 50 (residual 2.1 jumping straight from the "2" tier to the
 * "5" tier), leaving most of the chart's height empty above every real bar. */
function niceMax(value: number): number {
    // 1 specifically (the smallest value this can ever be called with -
    // rawMax is already floored at 1) has no integer strictly between 0 and
    // itself, so the y-axis's middle tick (scaleMax / 2, rounded) collides
    // with the top tick: both display "1", reading as a duplicated/wrong
    // label instead of a real midpoint. Bumping straight to 2 guarantees a
    // distinct middle tick (1) whenever the data is this sparse.
    if (value <= 1) return 2;
    if (value <= 5) return value;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const residual = value / magnitude;
    const niceResidual =
        residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 2.5 ? 2.5 : residual <= 5 ? 5 : 10;
    return niceResidual * magnitude;
}

/**
 * LoginTrendChart
 * ----------------------------
 * Daily login success/failure counts as a stacked bar chart, so an operator
 * (or a user checking their own activity) can spot a spike - a brute-force
 * run, a lockout wave - at a glance instead of paging/filtering through
 * individual rows below. Colors match this same page's own Result badges
 * (green=Success, red=Failed), not a new vocabulary. Deliberately a fixed
 * 14-day window with no controls of its own: a small trend glance, not a
 * second filterable table.
 *
 * Every bar is individually labeled with its day-of-month (not just the
 * first/last day) so a reader can read off which day a spike happened on
 * without guessing/counting bars. Hovering (or focusing via keyboard) a bar
 * lifts it slightly and opens a floating tooltip with the full date and
 * exact success/failure counts - every value here is already reachable in
 * the security-log table below, so this is a glance-level enhancement, not
 * a data source of its own.
 */
const LoginTrendChart: React.FC<LoginTrendChartProps> = ({ data, isLoading, isError }) => {
    const { t } = useTranslation("audit_log");
    const language = useLanguageStore((s) => s.pageLanguage);
    // Day/month labels (formatDayLabel/formatAxisLabel below) use
    // chromeLanguage instead - see AllAuthorizationLogSection.tsx's matching
    // comment. Everything else here (the success/failure counts) is plain
    // numeral formatting, not a date, so it stays on the page language.
    const dateLanguage = useLanguageStore((s) => s.chromeLanguage);
    const [hovered, setHovered] = useState<number | null>(null);

    if (isLoading) return <Skeleton height={`${CHART_HEIGHT + 70}px`} />;
    if (isError) return <FormAlert status="error">{t("security.failedToLoadTrend")}</FormAlert>;
    if (!data || data.length === 0) return null;

    const rawMax = Math.max(1, ...data.map((d) => d.success + d.failure));
    const scaleMax = niceMax(rawMax);
    const dayWidth = 100 / data.length;
    const barWidth = dayWidth * BAR_WIDTH_RATIO;
    const totalSuccess = data.reduce((sum, d) => sum + d.success, 0);
    const totalFailure = data.reduce((sum, d) => sum + d.failure, 0);
    const plotHeight = CHART_HEIGHT - 12;
    const hoveredPoint = hovered !== null ? data[hovered] : null;

    return (
        <Box>
            <Stack gap={1} mb={3}>
                <HStack gap={5} wrap="wrap">
                    <HStack gap={2}>
                        <Box w="12px" h="12px" borderRadius="3px" bg="green.500" />
                        <Text fontSize="sm" color="fg.muted">{t("security.successCount", { count: formatNumber(totalSuccess, language) })}</Text>
                    </HStack>
                    <HStack gap={2}>
                        <Box w="12px" h="12px" borderRadius="3px" bg="red.500" />
                        <Text fontSize="sm" color="fg.muted">{t("security.failedCount", { count: formatNumber(totalFailure, language) })}</Text>
                    </HStack>
                </HStack>
                <Text fontSize="xs" color="fg.muted">
                    {formatDayLabel(data[0].date, dateLanguage)} to {formatDayLabel(data[data.length - 1].date, dateLanguage)}
                </Text>
            </Stack>

            <HStack align="stretch" gap={2}>
                {/* Y-axis: 0 / half / max, evenly spaced against the same
                    plotHeight the bars themselves scale against. */}
                <Stack justify="space-between" h={`${CHART_HEIGHT}px`} w={`${Y_AXIS_WIDTH}px`} flexShrink={0} pb="12px">
                    <Text fontSize="xs" color="fg.muted" textAlign="right">{formatNumber(scaleMax, language)}</Text>
                    <Text fontSize="xs" color="fg.muted" textAlign="right">{formatNumber(Math.round(scaleMax / 2), language)}</Text>
                    <Text fontSize="xs" color="fg.muted" textAlign="right">{formatNumber(0, language)}</Text>
                </Stack>

                <Box flex="1" minW={0} position="relative">
                    {hoveredPoint && (
                        <Box
                            position="absolute"
                            top="0"
                            left={`${hovered! * dayWidth + dayWidth / 2}%`}
                            transform="translate(-50%, -100%)"
                            bg="bg.surface"
                            borderWidth="1px"
                            borderColor="border.default"
                            rounded="md"
                            shadow="md"
                            px={3}
                            py={2}
                            zIndex={1}
                            pointerEvents="none"
                            whiteSpace="nowrap"
                        >
                            <Text fontSize="sm" fontWeight="semibold" mb={1}>
                                {formatDayLabel(hoveredPoint.date, dateLanguage)}
                            </Text>
                            <HStack gap={1.5}>
                                <Box w="8px" h="8px" borderRadius="2px" bg="green.500" />
                                <Text fontSize="xs" color="fg.muted">{t("security.successLabel")}</Text>
                                <Text fontSize="xs" fontWeight="semibold">{formatNumber(hoveredPoint.success, language)}</Text>
                            </HStack>
                            <HStack gap={1.5}>
                                <Box w="8px" h="8px" borderRadius="2px" bg="red.500" />
                                <Text fontSize="xs" color="fg.muted">{t("security.failedLabel")}</Text>
                                <Text fontSize="xs" fontWeight="semibold">{formatNumber(hoveredPoint.failure, language)}</Text>
                            </HStack>
                        </Box>
                    )}

                    <svg
                        width="100%"
                        height={CHART_HEIGHT}
                        role="img"
                        aria-label={t("security.chartAriaLabel", {
                            days: formatNumber(data.length, language),
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
                                stroke="var(--chakra-colors-border-default)"
                                strokeWidth="1"
                            />
                        ))}
                        {/* X axis and Y axis, solid and one step more visible than the gridlines above. */}
                        <line
                            x1="0" y1={CHART_HEIGHT - 0.5} x2="100%" y2={CHART_HEIGHT - 0.5}
                            stroke="var(--chakra-colors-fg-muted)" strokeWidth="1"
                        />
                        <line
                            x1="0.5" y1="0" x2="0.5" y2={CHART_HEIGHT}
                            stroke="var(--chakra-colors-fg-muted)" strokeWidth="1"
                        />
                        {data.map((point, i) => {
                            const total = point.success + point.failure;
                            const barHeight = (total / scaleMax) * plotHeight;
                            const failureHeight = total === 0 ? 0 : (point.failure / total) * barHeight;
                            const successHeight = barHeight - failureHeight;
                            const x = i * dayWidth + (dayWidth - barWidth) / 2;
                            const isHovered = hovered === i;

                            return (
                                <g
                                    key={point.date}
                                    tabIndex={0}
                                    style={{ outline: "none", cursor: "pointer" }}
                                    onMouseEnter={() => setHovered(i)}
                                    onMouseLeave={() => setHovered(null)}
                                    onFocus={() => setHovered(i)}
                                    onBlur={() => setHovered(null)}
                                >
                                    {/* Wider transparent hit area than the bar itself, so a thin/zero-height bar is still hoverable/focusable. */}
                                    <rect x={`${i * dayWidth}%`} y={0} width={`${dayWidth}%`} height={CHART_HEIGHT} fill="transparent" />
                                    {successHeight > 0 && (
                                        <rect
                                            x={`${x}%`}
                                            y={CHART_HEIGHT - barHeight}
                                            width={`${barWidth}%`}
                                            height={successHeight}
                                            rx={2}
                                            fill="var(--chakra-colors-green-500)"
                                            opacity={isHovered ? 1 : 0.9}
                                        />
                                    )}
                                    {failureHeight > 0 && (
                                        <rect
                                            x={`${x}%`}
                                            y={CHART_HEIGHT - failureHeight}
                                            width={`${barWidth}%`}
                                            height={failureHeight}
                                            rx={2}
                                            fill="var(--chakra-colors-red-500)"
                                            opacity={isHovered ? 1 : 0.9}
                                        />
                                    )}
                                </g>
                            );
                        })}
                    </svg>

                    <HStack gap={0} mt={1}>
                        {data.map((point, i) => (
                            <Box key={point.date} w={`${dayWidth}%`} textAlign="center">
                                <Text
                                    fontSize="11px"
                                    whiteSpace="nowrap"
                                    color={hovered === i ? "fg.default" : "fg.muted"}
                                    fontWeight={hovered === i ? "semibold" : "normal"}
                                >
                                    {formatAxisLabel(point.date, dateLanguage)}
                                </Text>
                            </Box>
                        ))}
                    </HStack>
                </Box>
            </HStack>
        </Box>
    );
};

export default LoginTrendChart;
