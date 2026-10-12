import type React from "react";

/** Only a plain string/number render result can safely become a `title`
 * tooltip - anything else (badges, buttons, a name+badge Text node) is a
 * React element, not text, and can't be stringified without risk. */
export function plainTextOf(node: React.ReactNode): string | undefined {
    if (typeof node === "string" || typeof node === "number") return String(node);
    return undefined;
}

// The scroll-shadow gradients and custom scrollbar colors live in
// theme/tailwind.css's .data-table-scroll-area class: ::-webkit-scrollbar
// and stacked multi-attachment backgrounds have no Tailwind utility
// equivalent, so this needs a real CSS class rather than inline classes.
export const SCROLL_AREA_CLASS = "data-table-scroll-area";

// Applied to every header cell, not the <tr> (sticky on a table row is
// unreliable cross-browser), so headers stay put as the body scrolls under
// them. Only matters once the scroll area's max-height constrains height.
//
// Must be an opaque color, not an alpha tint: a translucent background
// composites over whatever scrolls underneath, so scrolled-past rows show
// through the "sticky" header instead of being hidden behind it. bg-bg-table-header
// is a step darker than DataTableRow.tsx's hover color (bg-muted), so the
// header reads as clearly its own darker strip rather than blending into a
// hovered row.
export const STICKY_HEADER_CELL_CLASS = "sticky top-0 z-10 h-11 font-semibold text-fg-default bg-bg-table-header border-b-2 border-border-strong shadow-[0_1px_0_var(--border-strong)]";
