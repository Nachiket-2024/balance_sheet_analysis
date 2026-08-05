import React from "react";
import { Button, type ButtonProps } from "@chakra-ui/react";

// gray/red/green cover every colorPalette this app currently passes to a
// row-action button (Edit/Policies use none -> gray; Delete/Purge -> red;
// Reactivate -> green). Each carries its own filled background (not just an
// outline on transparent) so the button reads as a raised control against a
// striped table row in both modes, plus a border one step darker/lighter
// than that fill so the edge stays visible against it, and a hover state
// that darkens/lightens both the fill and the border together for a clear,
// two-part state change rather than a barely-different background alone.
const PALETTE_STYLES = {
    // Edit/Policies (the two most-used row actions) live here. Now mirrors
    // red's own hover: a full solid fill plus a contrasting text color, not
    // just a lighter/darker shade of the same tint - "fills up" the same
    // way Delete does instead of merely shifting value. Light and dark
    // solid fills sit at opposite ends of the gray scale (gray.600 vs.
    // gray.300), so each needs its own contrasting hover text (white vs.
    // gray.900) rather than sharing one hoverColor like red does.
    gray: {
        border: "gray.500", hoverBorder: "gray.700",
        bg: "gray.100", hoverBg: "gray.600",
        borderDark: "gray.500", hoverBorderDark: "gray.300",
        bgDark: "gray.700", hoverBgDark: "gray.300",
        color: "fg.default", hoverColor: "white",
        hoverColorDark: "gray.900",
    },
    // Solid fill (not just a light tint) on hover, plus white text: a
    // stronger cue than the other palettes deliberately, since this is
    // used for destructive actions (Delete/Purge).
    red: {
        border: "red.400", hoverBorder: "red.500",
        bg: "red.50", hoverBg: "red.500",
        borderDark: "red.400", hoverBorderDark: "red.600",
        bgDark: "red.950", hoverBgDark: "red.600",
        color: "fg.error", hoverColor: "white",
        hoverColorDark: "white",
    },
    green: {
        border: "green.400", hoverBorder: "green.500",
        bg: "green.50", hoverBg: "green.100",
        borderDark: "green.400", hoverBorderDark: "green.700",
        bgDark: "green.950", hoverBgDark: "green.900",
        color: "fg.success", hoverColor: undefined,
        hoverColorDark: undefined,
    },
} as const;

/**
 * Per-row table action button (Edit, Policies, Delete, ...). Plain
 * variant="outline" defaults to Chakra's gray colorPalette, whose border
 * (gray.200/gray.800) and hover fill (gray.100/gray.900) sit right on top
 * of this app's own bg.surface/bg.canvas and a striped table's alternating
 * row color - so the button reads as plain text until you already know
 * it's clickable. These are deliberately higher-contrast, fixed values
 * instead. variant="plain" (not "outline") side-steps the outline recipe's
 * own built-in _hover, which fights with any hover style set here (see
 * LoginForm's Clear button history for why).
 */
const TableActionButton: React.FC<ButtonProps> = ({ colorPalette, ...rest }) => {
    const palette = PALETTE_STYLES[(colorPalette as keyof typeof PALETTE_STYLES) ?? "gray"] ?? PALETTE_STYLES.gray;

    return (
        <Button
            size="xs"
            // xs's stock textStyle is 12px - a bit small for how often these
            // (Edit/Delete/Policies/Log out/...) get read and clicked across
            // every table in the app. Bumped once here so every row-action
            // button gets it uniformly, instead of each call site pasting
            // its own fontSize override (some did, some didn't, so sizes
            // drifted between tables).
            fontSize="14px"
            variant="plain"
            borderWidth="1px"
            borderColor={palette.border}
            bg={palette.bg}
            color={palette.color}
            _hover={{ bg: palette.hoverBg, borderColor: palette.hoverBorder, color: palette.hoverColor }}
            _dark={{
                borderColor: palette.borderDark,
                bg: palette.bgDark,
                _hover: { bg: palette.hoverBgDark, borderColor: palette.hoverBorderDark, color: palette.hoverColorDark },
            }}
            {...rest}
        />
    );
};

export default TableActionButton;
