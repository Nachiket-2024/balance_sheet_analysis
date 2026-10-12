import React from "react";
import { ShieldCheck, ShieldOff, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import StatTile from "../ui/cards/StatTile";
import { isDestructiveAction } from "../authorization/destructiveActions";
import type { PolicyRead } from "../api/policies_api";

export type PolicyStatTileKey = "total" | "active" | "inactive" | "destructive";

interface PolicyStatsCardProps {
  policies: PolicyRead[] | undefined;
  isLoading: boolean;
  onFilterTotal?: () => void;
  onFilterActive?: () => void;
  onFilterInactive?: () => void;
  onFilterDestructive?: () => void;
  activeTile?: PolicyStatTileKey | null;
}

/**
 * PolicyStatsCard
 * ----------------------------
 * One row of brand-tinted tiles under PoliciesPage's title (design/
 * policies.html), replacing the old 2x2 blue/green/cyan/orange grid, which
 * broke design.md's "tell tiles apart by icon, not by a fixed hue per
 * category" rule. Each tile also acts as a quick filter, mirroring
 * UserStatsCard: clicking Active/Inactive applies that status filter, and
 * "Grant destructive actions" filters to policies holding at least one
 * destructive action (isDestructiveAction) - more useful than the old
 * "distinct actions" count, which didn't lead anywhere.
 */
const PolicyStatsCard: React.FC<PolicyStatsCardProps> = ({
  policies,
  isLoading,
  onFilterTotal,
  onFilterActive,
  onFilterInactive,
  onFilterDestructive,
  activeTile,
}) => {
  const { t } = useTranslation("policies");
  const total = policies?.length;
  const active = policies?.filter((p) => p.is_active).length;
  const inactive = policies?.filter((p) => !p.is_active).length;
  const destructive = policies?.filter((p) =>
    p.actions.some(isDestructiveAction),
  ).length;

  return (
    <div className="flex items-stretch flex-wrap gap-3">
      <StatTile
        icon={<ShieldCheck size={18} aria-hidden="true" />}
        label={t("policies:statsCard.totalPolicies")}
        value={total}
        isLoading={isLoading}
        onClick={onFilterTotal}
        ariaLabel={t("policies:statsCard.totalPolicies")}
        pressed={activeTile === "total"}
      />
      <StatTile
        icon={<ShieldCheck size={18} aria-hidden="true" />}
        label={t("policies:statsCard.active")}
        value={active}
        isLoading={isLoading}
        onClick={onFilterActive}
        ariaLabel={t("policies:statsCard.active")}
        pressed={activeTile === "active"}
      />
      <StatTile
        icon={<ShieldOff size={18} aria-hidden="true" />}
        label={t("policies:statsCard.inactive")}
        value={inactive}
        isLoading={isLoading}
        onClick={onFilterInactive}
        ariaLabel={t("policies:statsCard.inactive")}
        pressed={activeTile === "inactive"}
      />
      <StatTile
        icon={<TriangleAlert size={18} aria-hidden="true" />}
        label={t("policies:statsCard.destructive")}
        value={destructive}
        isLoading={isLoading}
        onClick={onFilterDestructive}
        ariaLabel={t("policies:statsCard.destructive")}
        pressed={activeTile === "destructive"}
      />
    </div>
  );
};

export default PolicyStatsCard;
