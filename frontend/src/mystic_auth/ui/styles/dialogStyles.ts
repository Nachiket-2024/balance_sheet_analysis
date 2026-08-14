// Chakra's Dialog.Content defaults to bg: "bg.panel" (white in light mode)
// with just a boxShadow: "lg" - no border. Sitting over a page that's also
// mostly white/near-white (bg.canvas, Card's bg.surface), that shadow alone
// wasn't enough separation and the dialog read as blending into the page
// behind it. A visible border plus a stronger shadow, and a blurred/darker
// backdrop, is the standard "elevated panel over a dimmed page" treatment.
// The dialog machine sets `document.body { pointer-events: none }` while
// open (to make the real page behind it inert) and only opts the dialog
// *content* back in to `pointer-events: auto`. The backdrop inherits that
// `none` from body since nothing here overrode it, so without this the
// visible area around the dialog silently swallows clicks instead of
// dismissing it - "click anywhere in the background to close" didn't work.
export const DIALOG_BACKDROP_PROPS = {
    bg: "blackAlpha.600",
    backdropFilter: "blur(2px)",
    pointerEvents: "auto",
};

// Chakra's own Dialog recipe already defaults placement="top" (so the
// positioner aligns content to flex-start), but it pairs that with a
// content margin (`my`) of spacing.16 - 4rem (64px) above AND below the
// dialog. Two 64px margins is over a fifth of a 600px-tall laptop viewport
// gone before a single field renders, so a modestly tall form
// (PolicyFormDialog's 5 fields) ends up needing the positioner's own
// scroll (scrollBehavior defaults to "outside", i.e. the whole
// backdrop+dialog scrolls, not just the dialog body) even though the form
// itself isn't that long. Overriding `my` down to a few rem reclaims that
// space directly instead of adding still more offset on top of it.
export const DIALOG_CONTENT_PROPS = {
    borderWidth: "1px",
    borderColor: "border.default",
    boxShadow: "2xl",
    my: { base: "3", md: "4" },
};
