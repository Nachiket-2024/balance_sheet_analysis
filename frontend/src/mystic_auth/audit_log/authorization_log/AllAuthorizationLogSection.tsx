import React, { useState } from "react";
import { Input } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { SEARCH_INPUT_PROPS } from "../../ui/styles/inputStyles";
import { useAuthorizationAuditLogQuery } from "./authorizationLogQueries";
import { getAuthorizationColumns } from "./authorizationLogColumns";
import AuthorizationFilterBar from "./AuthorizationFilterBar";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";
import { useLanguageStore } from "../../store/languageStore";

interface AllAuthorizationLogSectionProps {
    /** See AuthorizationFilterBar's docstring. */
    extraResourceTypes?: string[];
    extraActions?: string[];
}

/** "Authorization decisions" tab's "All users" sub-tab (policies:read only):
 * same shape as MyAuthorizationLogSection, plus a server-side email search. */
const AllAuthorizationLogSection: React.FC<AllAuthorizationLogSectionProps> = ({
    extraResourceTypes, extraActions,
}) => {
    const { t } = useTranslation("audit_log");
    // chromeLanguage, not pageLanguage: this "when" column's dates/month
    // names should read the same way navbar/sidebar chrome does - always
    // English, except in a plain (non-mixed) hi/mr mode - not the
    // page-content language, which is what's mixed in for "en+hi"/"en+mr".
    // See languageStore.ts's LanguageMode docstring.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const [search, setSearch] = useState("");
    const debouncedSearch = useDebouncedValue(search);
    const { sort, toggleSort } = useSortState("created_at");
    const [action, setAction] = useState(ALL_VALUE);
    const [resourceType, setResourceType] = useState(ALL_VALUE);
    const [allowed, setAllowed] = useState(ALL_VALUE);
    const [page, setPage] = usePageResetOn(
        `${debouncedSearch}|${sort.key}|${sort.direction}|${action}|${resourceType}|${allowed}`
    );

    const { data, isLoading, isError } = useAuthorizationAuditLogQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        action: action || undefined,
        resourceType: resourceType || undefined,
        allowed: toBoolFilter(allowed),
        sortBy: sort.key,
        sortDir: sort.direction,
    });
    const totalPages = totalPagesFor(data?.total ?? 0);

    return (
        <>
            <Input
                placeholder={t("authorization.searchPlaceholder")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                mb={4}
                maxW="sm"
                size="sm"
                {...SEARCH_INPUT_PROPS}
            />
            <AuthorizationFilterBar
                action={action} setAction={setAction}
                resourceType={resourceType} setResourceType={setResourceType}
                allowed={allowed} setAllowed={setAllowed}
                extraResourceTypes={extraResourceTypes}
                extraActions={extraActions}
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />
            <DataTable
                columns={getAuthorizationColumns(t, language)}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage={search ? t("authorization.emptySearch") : t("authorization.emptyFiltered")}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />
        </>
    );
};

export default AllAuthorizationLogSection;
