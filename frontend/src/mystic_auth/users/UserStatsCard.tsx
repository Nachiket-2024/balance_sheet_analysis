import React from "react";
import { SimpleGrid } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import Card from "../ui/Card";
import StatTile from "../ui/StatTile";
import { useUserStatsQuery } from "./userQueries";

interface UserStatsCardProps {
    /** Clears every filter, showing the unfiltered full list. */
    onFilterTotal?: () => void;
    /** Filters the table to verified users only. */
    onFilterVerified?: () => void;
    /** Filters the table to unverified users only. */
    onFilterUnverified?: () => void;
    /** Filters the table to inactive users only. */
    onFilterInactive?: () => void;
}

/**
 * UserStatsCard
 * ----------------------------
 * Summary counts (GET /users/stats) for UsersPage: total, verified,
 * unverified, inactive - always across the whole table, independent of
 * whatever page/search/filters the list below currently has applied, so
 * these numbers don't shift as an operator pages or filters through the list.
 * Sits in PageContainer's own actions slot (top-right, level with the page
 * title), so the search/filter row and table below it are unaffected.
 *
 * Each tile doubles as a filter shortcut when its handler is supplied:
 * clicking "Verified" applies the same filter an operator would otherwise set
 * by hand via the Verified select below, rather than just being a
 * read-only count next to it.
 */
const UserStatsCard: React.FC<UserStatsCardProps> = ({
    onFilterTotal, onFilterVerified, onFilterUnverified, onFilterInactive,
}) => {
    const { t } = useTranslation("users");
    const { data, isLoading, isError } = useUserStatsQuery();

    if (isError) return null;

    return (
        <Card p={4} w={{ base: "full", md: "280px" }}>
            <SimpleGrid columns={2} gap={4}>
                <StatTile
                    label={t("users:statsCard.totalUsers")} value={data?.total} isLoading={isLoading} onClick={onFilterTotal}
                    ariaLabel={t("users:statsCard.filterTotal")}
                />
                <StatTile
                    label={t("users:statsCard.verified")} value={data?.verified} isLoading={isLoading} color="green.500"
                    onClick={onFilterVerified} ariaLabel={t("users:statsCard.filterVerified")}
                />
                <StatTile
                    label={t("users:statsCard.unverified")} value={data?.unverified} isLoading={isLoading} color="yellow.500"
                    onClick={onFilterUnverified} ariaLabel={t("users:statsCard.filterUnverified")}
                />
                <StatTile
                    label={t("users:statsCard.inactive")} value={data?.inactive} isLoading={isLoading} color="red.500"
                    onClick={onFilterInactive} ariaLabel={t("users:statsCard.filterInactive")}
                />
            </SimpleGrid>
        </Card>
    );
};

export default UserStatsCard;
