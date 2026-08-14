import React from "react";
import { Button, type ButtonProps } from "@chakra-ui/react";

import { FAST_HOVER_TRANSITION } from "./styles/buttonStyles";

// red/green/orange/blue/purple cover every colorPalette this app currently
// passes to a row-action button (Delete/Purge -> red; Reactivate -> green;
// Edit -> orange; View -> blue; Policies -> purple). Each carries its own
// filled background (not just an
// outline on transparent) so the button reads as a raised control against a
// striped table row in both modes, plus a border one step darker/lighter
// than that fill so the edge stays visible against it, and a hover state
// that darkens/lightens both the fill and the border together for a clear,
// two-part state change rather than a barely-different background alone.
const PALETTE_STYLES = {
    // Solid fill (not just a light tint) on hover, plus white text: a
    // stronger cue than the other palettes deliberately, since this is
    // used for destructive actions (Delete/Purge).
    red: {
        border: "red.400", hoverBorder: "red.500",
        bg: "red.50", hoverBg: "red.500",
        borderDark: "red.400", hoverBorderDark: "red.600",
        bgDark: "red.950", hoverBgDark: "red.600",
        color: "fg.error", colorDark: undefined, hoverColor: "white",
        hoverColorDark: "white",
    },
    // Reactivate. Same solid-fill-on-hover shape as red/orange/blue/purple
    // below (not the light-tint-only hover it used to have) so every row
    // action "fills up" identically on hover instead of Reactivate alone
    // reading as a weaker, half-finished version of the others.
    green: {
        border: "green.400", hoverBorder: "green.600",
        bg: "green.50", hoverBg: "green.500",
        borderDark: "green.400", hoverBorderDark: "green.500",
        bgDark: "green.950", hoverBgDark: "green.600",
        color: "fg.success", colorDark: undefined, hoverColor: "white",
        hoverColorDark: "white",
    },
    // Edit. Light tint at rest, but fills fully solid with white text on
    // hover, same as red/green above, matching how Delete/Purge read as
    // "activated" rather than just a shade darker. Unlike red/green, there's
    // no fg.warning semantic token to lean on for a dark-aware base text
    // color, so colorDark is spelled out explicitly - orange.700 (tuned for
    // the light orange.50 chip) would be far too dark to read against this
    // same palette's dark orange.950 chip otherwise.
    orange: {
        border: "orange.400", hoverBorder: "orange.600",
        bg: "orange.50", hoverBg: "orange.500",
        borderDark: "orange.400", hoverBorderDark: "orange.500",
        bgDark: "orange.950", hoverBgDark: "orange.600",
        color: "orange.700", colorDark: "orange.200", hoverColor: "white",
        hoverColorDark: "white",
    },
    // View. Same solid-fill-on-hover treatment and same reasoning as orange
    // above for the explicit colorDark (no fg.info token to fall back on).
    blue: {
        border: "blue.400", hoverBorder: "blue.600",
        bg: "blue.50", hoverBg: "blue.500",
        borderDark: "blue.400", hoverBorderDark: "blue.500",
        bgDark: "blue.950", hoverBgDark: "blue.600",
        color: "blue.700", colorDark: "blue.200", hoverColor: "white",
        hoverColorDark: "white",
    },
    // Policies. Purple rather than reusing green/orange/blue so it reads as
    // its own deliberate action next to Edit/View/Delete, and distinct from
    // the app's own brand teal. Same solid-fill-on-hover shape and same
    // explicit-colorDark reasoning as orange/blue above.
    purple: {
        border: "purple.400", hoverBorder: "purple.600",
        bg: "purple.50", hoverBg: "purple.500",
        borderDark: "purple.400", hoverBorderDark: "purple.500",
        bgDark: "purple.950", hoverBgDark: "purple.600",
        color: "purple.700", colorDark: "purple.200", hoverColor: "white",
        hoverColorDark: "white",
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
type TableActionButtonProps = Omit<ButtonProps, "colorPalette"> & {
    colorPalette: keyof typeof PALETTE_STYLES;
};

const TableActionButton: React.FC<TableActionButtonProps> = ({ colorPalette, ...rest }) => {
    const palette = PALETTE_STYLES[colorPalette];

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
            transition={FAST_HOVER_TRANSITION}
            _hover={{ bg: palette.hoverBg, borderColor: palette.hoverBorder, color: palette.hoverColor }}
            _dark={{
                borderColor: palette.borderDark,
                bg: palette.bgDark,
                color: palette.colorDark,
                _hover: { bg: palette.hoverBgDark, borderColor: palette.hoverBorderDark, color: palette.hoverColorDark },
            }}
            {...rest}
        />
    );
};

export default TableActionButton;
