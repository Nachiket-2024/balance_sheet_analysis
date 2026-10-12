import React from "react";
import { Gauge, LockKeyhole, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { RateLimitSummary } from "../api/rate_limits_api";
import StatTile from "../ui/cards/StatTile";
import FormAlert from "../ui/feedback/FormAlert";

interface RateLimitsStatsCardProps {
    summary: RateLimitSummary | undefined;
    isLoading: boolean;
    isError: boolean;
    errorMessage?: string;
    activeTile: "all" | "at_limit" | "login_lockouts";
    onFilterTotal: () => void;
    onFilterAtLimit: () => void;
    onFilterLoginLockouts: () => void;
}

const RateLimitsStatsCard: React.FC<RateLimitsStatsCardProps> = ({ summary, isLoading, isError, errorMessage, activeTile, onFilterTotal, onFilterAtLimit, onFilterLoginLockouts }) => {
    const { t } = useTranslation("rate_limits");
    const tiles = [
        { icon: <Gauge size={18} aria-hidden="true" />, label: t("stats.total"), value: summary?.total, key: "all" as const, onClick: onFilterTotal },
        { icon: <TriangleAlert size={18} aria-hidden="true" />, label: t("stats.atLimit"), value: summary?.at_limit, key: "at_limit" as const, onClick: onFilterAtLimit },
        { icon: <LockKeyhole size={18} aria-hidden="true" />, label: t("stats.loginLockouts"), value: summary?.login_lockouts, key: "login_lockouts" as const, onClick: onFilterLoginLockouts },
    ];

    return (
        <div className="flex flex-col gap-2" aria-label={t("stats.label")}>
            {isError && errorMessage && <FormAlert status="error" size="sm">{errorMessage}</FormAlert>}
            <div className="flex items-stretch flex-wrap gap-3">
            {tiles.map((tile) => (
                <StatTile
                    key={tile.label}
                    icon={tile.icon}
                    label={tile.label}
                    value={tile.value}
                    isLoading={isLoading}
                    isError={isError}
                    onClick={tile.onClick}
                    ariaLabel={tile.label}
                    pressed={activeTile === tile.key}
                />
            ))}
            </div>
        </div>
    );
};

export default RateLimitsStatsCard;
