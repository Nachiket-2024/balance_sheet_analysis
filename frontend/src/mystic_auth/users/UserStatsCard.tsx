import React from "react";
import { BadgeCheck, MailWarning, UserX, Users as UsersIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import StatTile from "../ui/cards/StatTile";
import { useUserStatsQuery } from "./queries/userQueries";

export type UserStatTileKey = "total" | "verified" | "unverified" | "inactive";

interface UserStatsCardProps {
    /** Clears every filter, showing the unfiltered full list. */
    onFilterTotal?: () => void;
    /** Filters the table to verified users only. */
    onFilterVerified?: () => void;
    /** Filters the table to unverified users only. */
    onFilterUnverified?: () => void;
    /** Filters the table to deactivated users only. */
    onFilterInactive?: () => void;
    /** Which tile's own filter combination is currently applied, if any -
     * drives the pressed/brand-highlighted look (design/users.html's
     * `.tile[aria-pressed="true"]`), so the row also reads as "what this
     * table is filtered to" rather than just four buttons. */
    activeTile?: UserStatTileKey | null;
}

/**
 * UserStatsCard
 * ----------------------------
 * Summary counts (GET /users/stats) for UsersPage: total, verified,
 * unverified, inactive. Always reflects the whole table, not whatever
 * page/search/filters are currently applied, so the numbers don't shift as
 * an operator pages or filters through the list.
 *
 * One row of brand-tinted tiles under the page title (design/users.html:
 * "Stat tiles are one short row under the title, so the filters get the
 * full width instead of wrapping beside a tall stats card") - rendered via
 * UsersPage's `headerExtra`, not `actions`, so it spans the full width
 * instead of sitting narrow beside the title.
 *
 * Each tile also acts as a filter shortcut when its handler is supplied:
 * clicking "Verified" applies the same filter as the Verified select below,
 * and stays visually pressed while that filter (and only that filter) is
 * the active one.
 */
const UserStatsCard: React.FC<UserStatsCardProps> = ({
    onFilterTotal, onFilterVerified, onFilterUnverified, onFilterInactive, activeTile,
}) => {
    const { t } = useTranslation("users");
    const { data, isLoading, isError } = useUserStatsQuery();

    if (isError) return null;

    return (
        <div className="flex items-stretch flex-wrap gap-3">
            <StatTile
                icon={<UsersIcon size={18} aria-hidden="true" />}
                label={t("users:statsCard.totalUsers")}
                value={data?.total}
                isLoading={isLoading}
                isError={isError}
                onClick={onFilterTotal}
                ariaLabel={t("users:statsCard.filterTotal")}
                pressed={activeTile === "total"}
            />
            <StatTile
                icon={<BadgeCheck size={18} aria-hidden="true" />}
                label={t("users:statsCard.verified")}
                value={data?.verified}
                isLoading={isLoading}
                isError={isError}
                dotColor="var(--green-500)"
                onClick={onFilterVerified}
                ariaLabel={t("users:statsCard.filterVerified")}
                pressed={activeTile === "verified"}
            />
            <StatTile
                icon={<MailWarning size={18} aria-hidden="true" />}
                label={t("users:statsCard.unverified")}
                value={data?.unverified}
                isLoading={isLoading}
                isError={isError}
                dotColor="#eab308"
                onClick={onFilterUnverified}
                ariaLabel={t("users:statsCard.filterUnverified")}
                pressed={activeTile === "unverified"}
            />
            <StatTile
                icon={<UserX size={18} aria-hidden="true" />}
                label={t("users:statsCard.inactive")}
                value={data?.inactive}
                isLoading={isLoading}
                isError={isError}
                dotColor="var(--red-500)"
                onClick={onFilterInactive}
                ariaLabel={t("users:statsCard.filterInactive")}
                pressed={activeTile === "inactive"}
            />
        </div>
    );
};

export default UserStatsCard;
