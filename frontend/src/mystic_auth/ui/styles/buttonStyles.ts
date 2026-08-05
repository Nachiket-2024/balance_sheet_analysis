// Solid variant's default hover is only colorPalette.solid at 90% opacity -
// too subtle a shift to read as a hover state (originally fixed one-off on
// LoginForm's/PasswordResetRequestForm's own Login/submit buttons; extracted
// here so every other colorPalette="brand" solid button - Create Policy,
// Save changes, Assign, Verify Account, Signup, etc. - gets the identical
// fix instead of each needing its own copy of this override).
export const BRAND_SOLID_HOVER_PROPS = {
    _hover: { bg: "brand.700" },
};

// Same underlying problem as BRAND_SOLID_HOVER_PROPS, for an
// outline/colorPalette="brand" secondary action (e.g. "Send New
// Verification Link" below the primary "Verify Account" button): an
// outline button's stock hover only lightens its already-transparent
// background a shade, which reads as no change at all against the page's
// own bg.canvas. Fills solid brand on hover instead, the same "fills up"
// treatment SECONDARY_BUTTON_PROPS/ICON_BUTTON_PROPS use for their own
// too-faint hovers, just with the brand palette instead of gray since this
// keeps the button's own brand-colored border/text identity.
export const BRAND_OUTLINE_HOVER_PROPS = {
    _hover: { bg: "brand.500", color: "white" },
};

// Same fix as BRAND_SOLID_HOVER_PROPS above, for solid colorPalette="red"
// destructive actions (e.g. ConfirmDialog's confirm button) - the stock
// hover was too subtle a shift off red.600 to read as a real hover state.
export const DESTRUCTIVE_SOLID_HOVER_PROPS = {
    _hover: { bg: "red.700" },
};

// Dialog secondary actions (Cancel/Close). variant="ghost" (no border, no
// background) reads as plain text next to a solid primary action, and its
// hover is too faint to register as a real button - same class of issue
// TableActionButton.tsx and Pagination.tsx's identical fixes address for
// their own controls. Hover now fills solid (not just a lighter/darker
// shade) with a contrasting text color, the same "fills up" treatment
// TableActionButton.tsx's red palette (Delete/Purge) already had - light
// and dark solid fills sit at opposite ends of the gray scale, so each
// needs its own contrasting hover text (white vs. gray.900).
export const SECONDARY_BUTTON_PROPS = {
    variant: "plain" as const,
    borderWidth: "1px",
    borderColor: "gray.500",
    bg: "gray.100",
    color: "fg.default",
    _hover: { bg: "gray.600", borderColor: "gray.700", color: "white" },
    _dark: {
        borderColor: "gray.500",
        bg: "gray.700",
        _hover: { bg: "gray.300", borderColor: "gray.300", color: "gray.900" },
    },
};

// Navbar's icon-only controls (theme toggle, mobile menu toggle).
// variant="ghost" is invisible until hovered - no border, no background - so
// against Navbar's own bg.surface these read as bare icons, not controls,
// same issue SECONDARY_BUTTON_PROPS fixes for text buttons. Same solid-fill
// hover as SECONDARY_BUTTON_PROPS above (still includes a hover text color:
// ThemeToggle's/Navbar's glyphs are plain characters, not colored emoji
// images, so they do pick up `color`).
export const ICON_BUTTON_PROPS = {
    variant: "plain" as const,
    borderWidth: "1px",
    borderColor: "gray.500",
    bg: "gray.100",
    _hover: { bg: "gray.600", borderColor: "gray.700", color: "white" },
    _dark: {
        borderColor: "gray.500",
        bg: "gray.700",
        _hover: { bg: "gray.300", borderColor: "gray.300", color: "gray.900" },
    },
};
