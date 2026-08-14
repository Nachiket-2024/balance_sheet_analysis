import React, { useState } from "react";
import { useTranslation } from "react-i18next";

import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { useMyAuthorizationAuditLogQuery } from "./authorizationLogQueries";
import { getAuthorizationColumns } from "./authorizationLogColumns";
import AuthorizationFilterBar from "./AuthorizationFilterBar";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";
import { useLanguageStore } from "../../store/languageStore";

interface MyAuthorizationLogSectionProps {
    /** See AuthorizationFilterBar's docstring. */
    extraResourceTypes?: string[];
    extraActions?: string[];
}

/** "Authorization decisions" tab's "My activity" sub-tab: the caller's own
 * PBAC decisions only, no search (already scoped to one user). */
const MyAuthorizationLogSection: React.FC<MyAuthorizationLogSectionProps> = ({
    extraResourceTypes, extraActions,
}) => {
    const { t } = useTranslation("audit_log");
    // See AllAuthorizationLogSection.tsx's matching comment: dates/month
    // names use chromeLanguage, not pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const { sort, toggleSort } = useSortState("created_at");
    const [action, setAction] = useState(ALL_VALUE);
    const [resourceType, setResourceType] = useState(ALL_VALUE);
    const [allowed, setAllowed] = useState(ALL_VALUE);
    const [page, setPage] = usePageResetOn(`${sort.key}|${sort.direction}|${action}|${resourceType}|${allowed}`);

    const { data, isLoading, isError } = useMyAuthorizationAuditLogQuery(page, PAGE_SIZE, {
        action: action || undefined,
        resourceType: resourceType || undefined,
        allowed: toBoolFilter(allowed),
        sortBy: sort.key,
        sortDir: sort.direction,
    });

    return (
        <>
            <AuthorizationFilterBar
                action={action} setAction={setAction}
                resourceType={resourceType} setResourceType={setResourceType}
                allowed={allowed} setAllowed={setAllowed}
                extraResourceTypes={extraResourceTypes}
                extraActions={extraActions}
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mb={4} />
            <DataTable
                columns={getAuthorizationColumns(t, language)}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage={t("authorization.emptyFiltered")}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mt={4} />
        </>
    );
};

export default MyAuthorizationLogSection;
