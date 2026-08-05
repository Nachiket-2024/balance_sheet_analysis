import React, { useState } from "react";
import { Heading, Input } from "@chakra-ui/react";

import Card from "../../ui/Card";
import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { SEARCH_INPUT_PROPS } from "../../ui/styles/inputStyles";
import { useSecurityAuditLogQuery, useLoginTrendQuery } from "./queries";
import { securityColumns } from "./columns";
import SecurityFilterBar from "./SecurityFilterBar";
import LoginTrendChart from "./LoginTrendChart";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";

// Same reasoning as AllAuthorizationLogSection.tsx.
const AllSecurityLogSection: React.FC = () => {
    const [search, setSearch] = useState("");
    const debouncedSearch = useDebouncedValue(search);
    const { sort, toggleSort } = useSortState("created_at");
    const [eventType, setEventType] = useState(ALL_VALUE);
    const [ipAddress, setIpAddress] = useState(ALL_VALUE);
    const debouncedIpAddress = useDebouncedValue(ipAddress);
    const [success, setSuccess] = useState(ALL_VALUE);
    const [page, setPage] = usePageResetOn(
        `${debouncedSearch}|${sort.key}|${sort.direction}|${eventType}|${debouncedIpAddress}|${success}`
    );

    const { data, isLoading, isError } = useSecurityAuditLogQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        eventType: eventType || undefined,
        ipAddress: debouncedIpAddress || undefined,
        success: toBoolFilter(success),
        sortBy: sort.key,
        sortDir: sort.direction,
    });
    const totalPages = totalPagesFor(data?.total ?? 0);
    const trend = useLoginTrendQuery();

    return (
        <>
            <Card p={4} mb={4}>
                <Heading as="h3" size="md" mb={3}>Login activity</Heading>
                <LoginTrendChart data={trend.data} isLoading={trend.isLoading} isError={trend.isError} />
            </Card>
            <Input
                placeholder="Search by user email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                mb={4}
                maxW="sm"
                size="sm"
                {...SEARCH_INPUT_PROPS}
            />
            <SecurityFilterBar
                eventType={eventType} setEventType={setEventType}
                ipAddress={ipAddress} setIpAddress={setIpAddress}
                success={success} setSuccess={setSuccess}
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />
            <DataTable
                columns={securityColumns}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage={search ? "No security events match that search" : "No security events match these filters"}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />
        </>
    );
};

export default AllSecurityLogSection;
