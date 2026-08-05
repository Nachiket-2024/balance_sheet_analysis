import React, { useState } from "react";
import { Input } from "@chakra-ui/react";

import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { SEARCH_INPUT_PROPS } from "../../ui/styles/inputStyles";
import { useAuthorizationAuditLogQuery } from "./queries";
import { authorizationColumns } from "./columns";
import AuthorizationFilterBar from "./AuthorizationFilterBar";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";

/** "Authorization decisions" tab's "All users" sub-tab (policies:read only):
 * same shape as MyAuthorizationLog, plus a server-side email search. */
const AllAuthorizationLogSection: React.FC = () => {
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
                placeholder="Search by user email..."
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
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />
            <DataTable
                columns={authorizationColumns}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage={search ? "No authorization decisions match that search" : "No authorization decisions match these filters"}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />
        </>
    );
};

export default AllAuthorizationLogSection;
