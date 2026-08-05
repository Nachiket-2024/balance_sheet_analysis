import React from "react";
import { Button, HStack, Text } from "@chakra-ui/react";
import type { StackProps } from "@chakra-ui/react";

import { BRAND_SOLID_HOVER_PROPS } from "./styles/buttonStyles";

interface PaginationProps extends Omit<StackProps, "children" | "page" | "onChange"> {
    page: number;
    totalPages: number;
    onPageChange: (page: number) => void;
}

const ELLIPSIS = "…";

// variant="outline"'s stock border/hover (see TableActionButton.tsx and
// SEARCH_INPUT_PROPS's identical fix) is too close in value to bg.canvas in
// both modes to read as a distinct, clickable button sitting on the page.
// Fixed, higher-contrast values instead, plus an explicit background so
// each button reads as a raised control rather than bare text. Hover now
// fills solid with a contrasting text color - the same "fills up" treatment
// as TableActionButton.tsx's red palette (Delete/Purge) and
// SECONDARY_BUTTON_PROPS, rather than just a lighter/darker shade of the
// same tint.
const INACTIVE_PAGE_PROPS = {
    variant: "plain" as const,
    bg: "gray.100",
    borderWidth: "1px",
    borderColor: "gray.500",
    color: "fg.default",
    _hover: { bg: "gray.600", borderColor: "gray.700", color: "white" },
    _dark: {
        bg: "gray.700",
        borderColor: "gray.500",
        _hover: { bg: "gray.300", borderColor: "gray.300", color: "gray.900" },
    },
};

// Active page: brand.solid already has plenty of contrast on its own; this
// only adds a matching border so it doesn't look like a different kind of
// control next to its plain-styled siblings, plus the same hover fix every
// other colorPalette="brand" solid button uses (BRAND_SOLID_HOVER_PROPS) -
// the stock solid hover was too subtle to read as a real hover state here too.
const ACTIVE_PAGE_PROPS = {
    variant: "solid" as const,
    colorPalette: "brand" as const,
    borderWidth: "1px",
    borderColor: "brand.solid",
    ...BRAND_SOLID_HOVER_PROPS,
};

/**
 * Always includes page 1, the last page, and a window of `siblingCount`
 * pages around the current one, collapsing any gap into a single "…" -
 * the standard truncated numbered-pagination layout, so a 40-page list
 * doesn't render 40 buttons.
 */
function buildPageList(page: number, totalPages: number, siblingCount = 1): (number | typeof ELLIPSIS)[] {
    const pages: (number | typeof ELLIPSIS)[] = [];
    const start = Math.max(2, page - siblingCount);
    const end = Math.min(totalPages - 1, page + siblingCount);

    pages.push(1);
    if (start > 2) pages.push(ELLIPSIS);
    for (let p = start; p <= end; p++) pages.push(p);
    if (end < totalPages - 1) pages.push(ELLIPSIS);
    if (totalPages > 1) pages.push(totalPages);

    return pages;
}

/**
 * Numbered page navigation (1 2 3 ... N), meant to be rendered both above
 * and below a table so the user doesn't have to scroll back up to move
 * between pages. Always renders the same Prev/page/Next row - even for a
 * single page, where Prev/Next are simply disabled and "1" is the only
 * (already-active) page - rather than collapsing to nothing or to an
 * empty placeholder: either of those still risked a pixel or two of drift
 * against the real rendered row (borders, line-height) depending on
 * surrounding content, where rendering the identical structure every time
 * can't drift at all.
 */
const Pagination: React.FC<PaginationProps> = ({ page, totalPages, onPageChange, ...rest }) => {
    const pages = buildPageList(page, Math.max(1, totalPages));

    return (
        <HStack gap={2} justify="center" wrap="wrap" {...rest}>
            <Button
                size="sm"
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                aria-label="Previous page"
                {...INACTIVE_PAGE_PROPS}
            >
                Prev
            </Button>

            {pages.map((p, i) =>
                p === ELLIPSIS ? (
                    <Text key={`ellipsis-${i}`} px={1} color="fg.muted">
                        {ELLIPSIS}
                    </Text>
                ) : (
                    <Button
                        key={p}
                        size="sm"
                        minW="9"
                        onClick={() => onPageChange(p)}
                        aria-label={`Page ${p}`}
                        aria-current={p === page ? "page" : undefined}
                        {...(p === page ? ACTIVE_PAGE_PROPS : INACTIVE_PAGE_PROPS)}
                    >
                        {p}
                    </Button>
                )
            )}

            <Button
                size="sm"
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                aria-label="Next page"
                {...INACTIVE_PAGE_PROPS}
            >
                Next
            </Button>
        </HStack>
    );
};

export default Pagination;
