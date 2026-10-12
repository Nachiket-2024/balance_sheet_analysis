import React from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../styles/classNames";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

interface PaginationProps {
    page: number;
    totalPages: number;
    onPageChange: (page: number) => void;
    className?: string;
}

const ELLIPSIS = "…";

// Matches the app's other "fills solid on hover" buttons (TableActionButton,
// SearchInput's trigger): a plain bg + border reads as too close in value to
// bg-canvas to look clickable otherwise.
const INACTIVE_PAGE_CLASSES =
    "bg-gray-100 border border-gray-500 text-fg-default hover:bg-gray-600 hover:border-gray-700 hover:text-white " +
    "dark:bg-gray-700 dark:border-gray-500 dark:hover:bg-gray-300 dark:hover:border-gray-300 dark:hover:text-gray-900";

// brand.solid already has plenty of contrast; this adds a matching border so
// it doesn't look like a different control next to its plain-styled
// siblings, plus brand.800 on hover (BRAND_SOLID_HOVER_PROPS's fix).
const ACTIVE_PAGE_CLASSES = "bg-brand-solid text-brand-contrast border border-brand-solid hover:bg-brand-800";

const BASE_BUTTON_CLASSES =
    "h-8 min-w-9 px-2 rounded-md text-sm font-medium transition-colors duration-150 " +
    "disabled:pointer-events-none disabled:opacity-50";

/**
 * Always includes page 1, the last page, and a window of `siblingCount`
 * pages around the current one, collapsing any gap into a single "…", so a
 * 40-page list doesn't render 40 buttons.
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
 * Numbered page navigation (1 2 3 ... N), meant to render both above and
 * below a table so the user doesn't scroll back up to move between pages.
 * Always renders the same Prev/page/Next row, even for a single page (Prev/
 * Next simply disabled), rather than collapsing to a placeholder that could
 * drift a pixel or two from the real rendered row.
 */
const Pagination: React.FC<PaginationProps> = ({ page, totalPages, onPageChange, className }) => {
    const { t } = useTranslation("ui_text");
    // chromeLanguage, not pageLanguage: numerals stay ASCII even in a mixed
    // "en+hi" mode, same as dates (dateFormatters.ts). Only translated text
    // switches with pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const pages = buildPageList(page, Math.max(1, totalPages));

    return (
        <div className={cn("flex flex-wrap items-center justify-center gap-2", className)}>
            <button
                type="button"
                className={cn(BASE_BUTTON_CLASSES, INACTIVE_PAGE_CLASSES)}
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                aria-label={t("pagination.previousPage")}
            >
                {t("pagination.prev")}
            </button>

            {pages.map((p, i) =>
                p === ELLIPSIS ? (
                    <span key={`ellipsis-${i}`} className="px-1 text-fg-muted">
                        {ELLIPSIS}
                    </span>
                ) : (
                    <button
                        type="button"
                        key={p}
                        className={cn(BASE_BUTTON_CLASSES, p === page ? ACTIVE_PAGE_CLASSES : INACTIVE_PAGE_CLASSES)}
                        onClick={() => onPageChange(p)}
                        aria-label={t("pagination.page", { page: formatNumber(p, language) })}
                        aria-current={p === page ? "page" : undefined}
                    >
                        {formatNumber(p, language)}
                    </button>
                )
            )}

            <button
                type="button"
                className={cn(BASE_BUTTON_CLASSES, INACTIVE_PAGE_CLASSES)}
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                aria-label={t("pagination.nextPage")}
            >
                {t("pagination.next")}
            </button>
        </div>
    );
};

export default Pagination;
