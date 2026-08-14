import React, { useState } from "react";
import { Heading } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import Card from "../../ui/Card";
import DataTable from "../../ui/DataTable";
import Pagination from "../../ui/Pagination";
import { useDebouncedValue } from "../../ui/hooks/useDebouncedValue";
import { useSortState } from "../../ui/hooks/useSortState";
import { usePageResetOn } from "../../ui/hooks/usePageResetOn";
import { useMySecurityAuditLogQuery, useMyLoginTrendQuery } from "./securityLogQueries";
import { getSecurityColumns } from "./securityLogColumns";
import SecurityFilterBar from "./SecurityFilterBar";
import LoginTrendChart from "./LoginTrendChart";
import { ALL_VALUE, PAGE_SIZE, toBoolFilter, totalPagesFor } from "../auditLogListConfig";
import { useLanguageStore } from "../../store/languageStore";

/** "Security events" tab's "My activity" sub-tab: the caller's own login/
 * logout/lifecycle events, plus their own login-trend chart. */
const MySecurityLogSection: React.FC = () => {
    const { t } = useTranslation("audit_log");
    // See AllAuthorizationLogSection.tsx's matching comment: dates/month
    // names use chromeLanguage, not pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const { sort, toggleSort } = useSortState("created_at");
    const [eventType, setEventType] = useState(ALL_VALUE);
    const [ipAddress, setIpAddress] = useState(ALL_VALUE);
    const debouncedIpAddress = useDebouncedValue(ipAddress);
    const [success, setSuccess] = useState(ALL_VALUE);
    const [page, setPage] = usePageResetOn(
        `${sort.key}|${sort.direction}|${eventType}|${debouncedIpAddress}|${success}`
    );

    const { data, isLoading, isError } = useMySecurityAuditLogQuery(page, PAGE_SIZE, {
        eventType: eventType || undefined,
        ipAddress: debouncedIpAddress || undefined,
        success: toBoolFilter(success),
        sortBy: sort.key,
        sortDir: sort.direction,
    });
    const trend = useMyLoginTrendQuery();

    return (
        <>
            <Card p={4} mb={4}>
                <Heading as="h3" size="md" mb={3}>{t("security.loginActivity")}</Heading>
                <LoginTrendChart data={trend.data} isLoading={trend.isLoading} isError={trend.isError} />
            </Card>
            <SecurityFilterBar
                eventType={eventType} setEventType={setEventType}
                ipAddress={ipAddress} setIpAddress={setIpAddress}
                success={success} setSuccess={setSuccess}
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mb={4} />
            <DataTable
                columns={getSecurityColumns(t, language)}
                rows={data?.rows}
                rowKey={(e) => e.id}
                isLoading={isLoading}
                isError={isError}
                emptyMessage={t("security.emptyFiltered")}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />
            <Pagination page={page} totalPages={totalPagesFor(data?.total ?? 0)} onPageChange={setPage} mt={4} />
        </>
    );
};

export default MySecurityLogSection;
