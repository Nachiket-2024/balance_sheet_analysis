import React from "react";
import { CircleDashed, KeyRound, Layers, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import StatTile from "../ui/cards/StatTile";
import { isDestructiveAction } from "../authorization/destructiveActions";
import type {
  PermissionCatalogEntry,
  PermissionUsageEntry,
} from "../api/permissions_api";

export type PermissionStatTileKey = "total" | "destructive" | "unused";

interface PermissionsStatsCardProps {
  catalog: PermissionCatalogEntry[] | undefined;
  usage: PermissionUsageEntry[] | undefined;
  catalogLoading: boolean;
  catalogError: boolean;
  usageLoading: boolean;
  usageError: boolean;
  activeTile: PermissionStatTileKey | null;
  onFilterTotal: () => void;
  onFilterDestructive: () => void;
  onFilterUnused: () => void;
}

/**
 * PermissionsStatsCard
 * ----------------------------
 * One row of brand-tinted tiles under PermissionsPage's title
 * (design/permissions.html), replacing the old 2x2 orange/cyan card, which
 * broke design.md's "tell tiles apart by icon, not a fixed hue per
 * category" rule (see .project/permissions-page-review.md's suggestions).
 * Each tile also acts as a quick filter, same pattern as PolicyStatsCard:
 * clicking Destructive/Unused applies PermissionsPage's matching quick
 * filter.
 *
 * Each tile only becomes actionable after the data that backs that tile has
 * been verified. Catalog-backed tiles do not wait for holder usage, while
 * the unused tile remains unavailable until holder usage succeeds.
 */
const PermissionsStatsCard: React.FC<PermissionsStatsCardProps> = ({
  catalog,
  usage,
  catalogLoading,
  catalogError,
  usageLoading,
  usageError,
  activeTile,
  onFilterTotal,
  onFilterDestructive,
  onFilterUnused,
}) => {
  const { t } = useTranslation("permissions");

  const total = catalog?.length;
  const resourceTypes = catalog
    ? new Set(catalog.map((entry) => entry.resource_type)).size
    : undefined;
  const destructive = catalog?.filter((entry) =>
    isDestructiveAction(entry.action),
  ).length;
  const usageByAction = new Map(
    (usage ?? []).map((entry) => [entry.action, entry]),
  );
  const unused = !usageError && catalog
    ? catalog.filter(
        (entry) =>
          (usageByAction.get(entry.action)?.total_user_count ?? 0) === 0,
      ).length
    : undefined;

  const catalogUnavailable = catalogError || catalog === undefined;
  const usageUnavailable = usageError || usage === undefined;

  return (
    <div className="flex items-stretch gap-3 flex-wrap">
      <StatTile
        icon={<KeyRound size={18} aria-hidden="true" />}
        label={t("permissions:statsCard.totalActions")}
        value={catalogUnavailable ? undefined : total}
        isLoading={catalogLoading}
        onClick={catalogUnavailable || catalogLoading ? undefined : onFilterTotal}
        ariaLabel={t("permissions:statsCard.totalActions")}
        pressed={activeTile === "total"}
      />
      <StatTile
        icon={<Layers size={18} aria-hidden="true" />}
        label={t("permissions:statsCard.resourceTypes")}
        value={catalogUnavailable ? undefined : resourceTypes}
        isLoading={catalogLoading}
        ariaLabel={t("permissions:statsCard.resourceTypes")}
        pressed={false}
      />
      <StatTile
        icon={<TriangleAlert size={18} aria-hidden="true" />}
        label={t("permissions:statsCard.destructive")}
        value={catalogUnavailable ? undefined : destructive}
        isLoading={catalogLoading}
        onClick={catalogUnavailable || catalogLoading ? undefined : onFilterDestructive}
        ariaLabel={t("permissions:statsCard.destructive")}
        pressed={activeTile === "destructive"}
      />
      <StatTile
        icon={<CircleDashed size={18} aria-hidden="true" />}
        label={t("permissions:statsCard.unused")}
        value={catalogUnavailable || usageUnavailable ? undefined : unused}
        isLoading={catalogLoading || usageLoading}
        onClick={catalogUnavailable || usageUnavailable || catalogLoading || usageLoading ? undefined : onFilterUnused}
        ariaLabel={t("permissions:statsCard.unused")}
        pressed={activeTile === "unused"}
      />
    </div>
  );
};

export default PermissionsStatsCard;
