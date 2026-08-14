import React from "react";
import { Box, Skeleton, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { useLanguageStore } from "../store/languageStore";
import { formatNumber } from "../translations/numerals";

export interface StatTileProps {
    label: string;
    value: number | undefined;
    isLoading: boolean;
    color?: string;
    /** Applies a filter (or other action) tied to this tile when given - the
     * tile becomes a clickable shortcut instead of a read-only number. Omit
     * for a tile with no corresponding action. */
    onClick?: () => void;
    /** Overrides the default `Filter: {label}` aria-label used when onClick
     * is given, for callers that want more specific wording. */
    ariaLabel?: string;
}

// NOT the same solid-fill hover TableActionButton/Pagination use: those
// only ever hold one text color, so swapping to a solid fill + a single
// inverted hover text color works there. A stat tile holds several colors
// at once (a green/yellow/red/default number plus a separately-muted
// label), and a solid gray.600/gray.300 fill washed both of those out
// (dark text vanishing on a dark fill, light text on a light one) - this
// was the actual bug report. `brand.subtle`/`brand.selected` are the
// app's own existing "highlighted without inverting" language (see
// Sidebar's active-link background), a light tinted wash designed to sit
// behind existing text colors rather than replace them, so every number's
// own color and the muted label both stay exactly as readable as at rest.
const STAT_TILE_HOVER_PROPS = {
    borderWidth: "1px",
    borderColor: "transparent",
    transition: "background 0.15s ease, border-color 0.15s ease",
    _hover: { bg: "brand.selected", borderColor: "brand.solid" },
};

/**
 * StatTile
 * ----------------------------
 * A single labeled number in a summary card (UserStatsCard, PolicyStatsCard):
 * a large colored value with a muted label beneath it, optionally clickable.
 */
const StatTile: React.FC<StatTileProps> = ({ label, value, isLoading, color = "fg.default", onClick, ariaLabel }) => {
    const { t } = useTranslation("ui_text");
    const language = useLanguageStore((s) => s.pageLanguage);
    return (
    <Box
        textAlign="center"
        rounded="md"
        py={1}
        {...(onClick && {
            as: "button",
            type: "button",
            onClick,
            cursor: "pointer",
            "aria-label": ariaLabel ?? t("filterLabel", { label }),
            ...STAT_TILE_HOVER_PROPS,
        })}
    >
        {isLoading ? (
            <Skeleton height="30px" mx="auto" w="48px" />
        ) : (
            <Text fontSize="28px" fontWeight="bold" color={color} lineHeight="1">
                {formatNumber(value, language)}
            </Text>
        )}
        <Text fontSize="16px" color="fg.muted" mt={1} whiteSpace="nowrap">
            {label}
        </Text>
    </Box>
    );
};

export default StatTile;
