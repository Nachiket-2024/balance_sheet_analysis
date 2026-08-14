import React from "react";
import { SimpleGrid } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { Card } from "../sdk";
import { StatTile } from "../app_sdk";
import { useCompanyStatsQuery } from "./companyQueries";

interface CompanyStatsCardProps {
    /** Clears every filter, showing the unfiltered full list. */
    onFilterTotal?: () => void;
    /** Filters the table to companies with no parent (group roots) only. */
    onFilterGroupRoots?: () => void;
    /** Filters the table to companies with a parent (subsidiaries) only. */
    onFilterSubsidiaries?: () => void;
}

/**
 * Server-side scoped counts for CompaniesPage, independent of current
 * pagination, search, or hierarchy filter. The distinct group count was
 * dropped because it matches group roots in a healthy hierarchy.
 */
const CompanyStatsCard: React.FC<CompanyStatsCardProps> = ({
    onFilterTotal, onFilterGroupRoots, onFilterSubsidiaries,
}) => {
    const { t } = useTranslation("companies");
    const { data, isLoading, isError } = useCompanyStatsQuery();

    if (isError) return null;

    return (
        <Card
            p={4}
            w={{ base: "full", md: "420px" }}
            h="full"
            display="flex"
            flexDirection="column"
            justifyContent="center"
        >
            <SimpleGrid columns={3} gap={4}>
                <StatTile
                    label={t("totalCompanies")} value={data?.total} isLoading={isLoading} color="brand.fg"
                    onClick={onFilterTotal} ariaLabel={t("filterTotalCompaniesAria")}
                />
                <StatTile
                    label={t("groupRoots")} value={data?.group_roots} isLoading={isLoading} color="green.500"
                    onClick={onFilterGroupRoots} ariaLabel={t("filterGroupRootsAria")}
                />
                <StatTile
                    label={t("subsidiaries")} value={data?.subsidiaries} isLoading={isLoading} color="purple.500"
                    onClick={onFilterSubsidiaries} ariaLabel={t("filterSubsidiariesAria")}
                />
            </SimpleGrid>
        </Card>
    );
};

export default CompanyStatsCard;
