import React, { Fragment } from "react";
import { ChevronRight } from "lucide-react";
import { Link as RouterLink } from "react-router";

export interface BreadcrumbEntry {
    label: string;
    /** Omit for the current/last page - rendered as plain text instead of a
     * link. The last entry always renders as the current page regardless of
     * whether it sets `to`. */
    to?: string;
}

interface BreadcrumbsProps {
    items: BreadcrumbEntry[];
}

/**
 * Reusable breadcrumb trail: an ordered `{ label, to? }` list, rendered as
 * links for every entry except the last, which always renders as the
 * current, non-clickable page. No page in this template needs one yet (the
 * nav is flat - see PageContainer's `breadcrumbs` prop) - this exists as a
 * ready-made pattern for the first nested/detail route.
 */
const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ items }) => {
    if (items.length === 0) return null;

    return (
        <nav aria-label="Breadcrumb" className="mb-2 text-sm text-fg-muted">
            <ol className="flex items-center gap-1.5">
                {items.map((item, index) => {
                    const isCurrent = index === items.length - 1;
                    return (
                        <Fragment key={item.to ?? item.label}>
                            <li>
                                {isCurrent || !item.to ? (
                                    <span aria-current={isCurrent ? "page" : undefined} className="font-medium text-fg-default">
                                        {item.label}
                                    </span>
                                ) : (
                                    <RouterLink to={item.to} className="hover:underline">
                                        {item.label}
                                    </RouterLink>
                                )}
                            </li>
                            {!isCurrent && (
                                <li aria-hidden="true">
                                    <ChevronRight size={14} />
                                </li>
                            )}
                        </Fragment>
                    );
                })}
            </ol>
        </nav>
    );
};

export default Breadcrumbs;
