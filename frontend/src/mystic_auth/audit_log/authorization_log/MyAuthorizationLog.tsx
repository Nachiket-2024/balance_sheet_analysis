import React, { useState } from "react";

import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { useMyAuthorizationAuditLogQuery } from "./queries";
import { authorizationColumns } from "./columns";
import AuthorizationFilterBar from "./AuthorizationFilterBar";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";

/** "Authorization decisions" tab's "My activity" sub-tab: the caller's own
 * PBAC decisions only, no search (already scoped to one user). */
const MyAuthorizationLog: React.FC = () => {
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
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mb={4} />
            <DataTable
                columns={authorizationColumns}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage="No authorization decisions match these filters"
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mt={4} />
        </>
    );
};

export default MyAuthorizationLog;
