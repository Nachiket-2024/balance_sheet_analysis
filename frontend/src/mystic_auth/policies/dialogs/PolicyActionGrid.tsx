import React, { useMemo, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import SearchInput from "../../ui/filters/SearchInput";
import Badge from "../../ui/badges/Badge";
import { cn } from "../../ui/styles/classNames";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { formatPolicyActionLabel } from "../policyCardHelpers";

type QuickFilter = "all" | "selected" | "destructive";

export interface PolicyActionGridOption {
  value: string;
  label: string;
}

interface PolicyActionGridProps {
  values: string[];
  onChange: (values: string[]) => void;
  options: PolicyActionGridOption[];
  ariaLabel: string;
  disabled?: boolean;
}

/**
 * PolicyActionGrid
 * ----------------------------
 * design/policies.html's create/edit dialog Actions tab: a toolbar with an
 * All/Selected/Destructive quick filter and a search box.
 * above the same `.agroup`/`.aitems` grouped-table layout PolicyActionGroups
 * uses for the read-only card/details views, except each row is a Switch
 * toggle instead of static text. Replaces ActionChipGroup, which had no
 * search for a resource type with a large action
 * count.
 *
 */
const PolicyActionGrid: React.FC<PolicyActionGridProps> = ({
  values,
  onChange,
  options,
  ariaLabel,
  disabled,
}) => {
  const { t } = useTranslation(["policies", "ui_text"]);
  const [search, setSearch] = useState("");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");

  const selectedSet = useMemo(() => new Set(values), [values]);
  const destructiveOptions = useMemo(
    () => options.filter((o) => isDestructiveAction(o.value)),
    [options],
  );

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return options.filter((o) => {
      if (q && !o.label.toLowerCase().includes(q)) return false;
      if (quickFilter === "selected") return selectedSet.has(o.value);
      if (quickFilter === "destructive") return isDestructiveAction(o.value);
      return true;
    });
  }, [options, search, quickFilter, selectedSet]);

  const actionRows = shown;

  const toggle = (value: string) => {
    if (selectedSet.has(value)) onChange(values.filter((v) => v !== value));
    else onChange([...values, value]);
  };


  if (disabled) {
    return (
      <p className="text-sm text-fg-muted">
        {t("policies:formDialog.selectResourceTypeFirst")}
      </p>
    );
  }

  if (options.length === 0) {
    return (
      <p className="text-sm text-fg-muted">
        {t("policies:formDialog.noActionsForResourceType")}
      </p>
    );
  }

  const segments: [QuickFilter, string, number][] = [
    ["all", t("policies:formDialog.quickFilterAll"), options.length],
    [
      "selected",
      t("policies:formDialog.quickFilterSelected"),
      values.filter((v) => options.some((o) => o.value === v)).length,
    ],
    [
      "destructive",
      t("policies:formDialog.quickFilterDestructive"),
      destructiveOptions.length,
    ],
  ];

  return (
    <div role="group" aria-label={ariaLabel}>
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <SearchInput
          placeholder={t("policies:formDialog.searchActionsPlaceholder")}
          value={search}
          onChange={setSearch}
          resultsLabel={() => ""}
          loadingLabel=""
          className="w-64"
        />
        <div className="flex items-center gap-2 flex-wrap">
          <div
            className="flex items-center gap-0 border border-border-strong rounded-lg bg-bg-surface overflow-hidden"
            role="radiogroup"
            aria-label={t("policies:formDialog.quickFilterLabel")}
          >
            {segments.map(([value, label, count], i) => {
              const on = quickFilter === value;
              return (
                <button
                  type="button"
                  key={value}
                  role="radio"
                  aria-checked={on}
                  onClick={() => setQuickFilter(value)}
                  className={cn(
                    "px-3 py-2 text-sm font-semibold cursor-pointer flex items-center gap-2 whitespace-nowrap",
                    i !== 0 && "border-l border-border-strong",
                    on
                      ? "text-brand-fg bg-brand-tile-subtle shadow-[inset_0_0_0_2px_var(--brand-solid)]"
                      : "text-fg-muted bg-transparent",
                  )}
                >
                  {label}
                  <span
                    className={cn(
                      "text-xs rounded-full px-1.5 min-w-5 text-center",
                      on
                        ? "text-white bg-brand-solid"
                        : "text-fg-muted bg-bg-muted",
                    )}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {actionRows.length === 0 ? (
        <p className="text-sm text-fg-muted">
          {t("policies:formDialog.noActionsMatchSearch")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-2 p-0.5 sm:grid-cols-2">
          {actionRows.map((option) => (
            <div
              key={option.value}
              className="flex min-w-0 cursor-pointer items-center justify-between gap-3 rounded-lg border border-border-default bg-bg-surface px-3 py-2.5"
              onClick={(event) => {
                if (!(event.target as HTMLElement).closest("[role='switch'],[data-slot='switch']")) toggle(option.value);
              }}
            >
              <div className="flex min-w-0 flex-1 flex-wrap items-start gap-2">
                <p className="min-w-0 flex-1 line-clamp-2 text-sm font-medium" title={option.label}>
                  {option.label}
                </p>
                {isDestructiveAction(option.value) && (
                  <Badge size="xs" colorPalette="red" variant="subtle" className="shrink-0 leading-none">
                    <TriangleAlert size={11} aria-hidden="true" />
                    {t("policies:formDialog.quickFilterDestructive")}
                  </Badge>
                )}
              </div>
              <span className={cn(
                "relative inline-flex h-[1.15rem] w-8 shrink-0 items-center rounded-full border border-transparent p-0.5 shadow-xs transition-all",
                selectedSet.has(option.value) ? "justify-end bg-[var(--green-600)]" : "justify-start bg-input dark:bg-input/80",
              )}>
                <span className="pointer-events-none block size-4 rounded-full bg-background dark:bg-foreground" />
                <input
                  type="checkbox"
                  role="switch"
                  checked={selectedSet.has(option.value)}
                  aria-label={formatPolicyActionLabel(option.value)}
                  onChange={() => toggle(option.value)}
                  className="absolute inset-0 z-10 m-0 cursor-pointer opacity-0"
                />
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PolicyActionGrid;
