import React from "react";
import { Building2, GitBranch, Network } from "lucide-react";
import { useTranslation } from "react-i18next";

import { StatTile } from "../app_sdk";
import { useCompanyStatsQuery } from "./companyQueries";

interface CompanyStatsCardProps {
    /** Clears every filter, showing the unfiltered full list. */
    onFilterTotal?: () => void;
    /** Filters the table to companies with no parent (group roots) only. */
    onFilterGroupRoots?: () => void;
    /** Filters the table to companies with a parent (subsidiaries) only. */
    onFilterSubsidiaries?: () => void;
    activeTile?: "total" | "roots" | "subsidiaries" | null;
}

/**
 * Server-side scoped counts for CompaniesPage, independent of current
 * pagination, search, or hierarchy filter. The distinct group count was
 * dropped because it matches group roots in a healthy hierarchy.
 */
const CompanyStatsCard: React.FC<CompanyStatsCardProps> = ({
    onFilterTotal, onFilterGroupRoots, onFilterSubsidiaries, activeTile,
}) => {
    const { t } = useTranslation("companies");
    const { data, isLoading, isError } = useCompanyStatsQuery();

    if (isError) return null;

    return (
        <div className="flex flex-wrap items-stretch gap-3">
            <StatTile
                icon={<Building2 size={18} aria-hidden="true" />}
                label={t("totalCompanies")} value={data?.total} isLoading={isLoading} onClick={onFilterTotal}
                ariaLabel={t("filterTotalCompaniesAria")} pressed={activeTile === "total"}
            />
            <StatTile
                icon={<Network size={18} aria-hidden="true" />}
                label={t("groupRoots")} value={data?.group_roots} isLoading={isLoading}
                onClick={onFilterGroupRoots} ariaLabel={t("filterGroupRootsAria")} pressed={activeTile === "roots"}
            />
            <StatTile
                icon={<GitBranch size={18} aria-hidden="true" />}
                label={t("subsidiaries")} value={data?.subsidiaries} isLoading={isLoading}
                onClick={onFilterSubsidiaries} ariaLabel={t("filterSubsidiariesAria")}
                pressed={activeTile === "subsidiaries"}
            />
        </div>
    );
};

export default CompanyStatsCard;
