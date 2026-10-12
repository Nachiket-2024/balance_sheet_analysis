import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { PolicyRead } from "../../api/policies_api";
import { toaster } from "../../ui/toaster/toasterInstance";
import { isDestructiveAction } from "../../authorization/destructiveActions";
import { canGrantAction } from "../../authorization/grantability";
import { useAuthorization } from "../../authorization/useAuthorization";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../policyCardHelpers";
import { usePermissionCatalogQuery } from "../queries/permissionQueries";
import type { PolicyFormValues } from "./PolicyFormDialog";

// Not in the permission catalog (it's not a real resource type any route is
// scoped to) but a real value PolicyRead.resource_type can hold: the
// baseline system_superuser policy is seeded with "*", meaning "every
// resource type." Without this, editing it showed an empty Resource type
// select (its value matched no catalog-derived option) and, worse, saving
// any other field cleared its resource_type to "" since handleResourceType
// Change never ran for it - see the bug this option exists to fix.
export const ALL_RESOURCE_TYPES_VALUE = "*";

interface UsePolicyFormStateParams {
  isOpen: boolean;
  policy?: PolicyRead;
  onSubmit: (values: PolicyFormValues) => void;
  onActionsChange?: (
    actions: string[],
    rollback: () => void,
    previousActions: string[],
    apply: () => void,
  ) => void;
  onClose: () => void;
  onDetails?: () => void;
}

/** All form state, derived options, and edit handlers behind
 * PolicyFormDialog: field state, the resource-type/action option lists
 * (scoped to what the catalog and the caller's own grantable actions
 * allow), the unsaved-changes dirty check, and submit. Split out of one
 * 402-line file, see AGENTS.md's ~350-line target. */
export function usePolicyFormState({
  isOpen,
  policy,
  onSubmit,
  onActionsChange,
  onClose,
  onDetails,
}: UsePolicyFormStateParams) {
  const { t } = useTranslation(["policies", "ui_text"]);
  const { can } = useAuthorization();
  const catalogQuery = usePermissionCatalogQuery(isOpen);
  const [tab, setTab] = useState<"basics" | "actions">("basics");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [actions, setActions] = useState<string[]>([]);
  const [resourceType, setResourceType] = useState("");
  const [conditionsEnabled, setConditionsEnabled] = useState(false);
  const [conditionsText, setConditionsText] = useState("");

  // Live, as the operator types - catches malformed JSON (or valid JSON
  // that isn't an object, e.g. an array or a bare string) before submit,
  // instead of only surfacing INVALID_CONDITIONS after a save round-trip.
  // Deeper semantic checks (unsupported keys, wrong value shapes - see
  // condition_validator.py) still only run server-side; this is just the
  // parse-level check the frontend can do cheaply and instantly.
  const conditionsError = useMemo(() => {
    if (!conditionsEnabled || !conditionsText.trim()) return null;
    let parsed: unknown;
    try {
      parsed = JSON.parse(conditionsText);
    } catch {
      return t("policies:formDialog.conditionsInvalidJson");
    }
    if (
      parsed === null ||
      typeof parsed !== "object" ||
      Array.isArray(parsed)
    ) {
      return t("policies:formDialog.conditionsInvalidJson");
    }
    return null;
  }, [conditionsEnabled, conditionsText, t]);

  const resourceTypeOptions = useMemo(() => {
    const types = new Set(
      (catalogQuery.data ?? []).map((entry) => entry.resource_type),
    );
    const options = Array.from(types).map((type) => ({
      value: type,
      label: formatResourceTypeLabel(type),
    }));
    // Only offered once it's actually in play (editing system_superuser,
    // or any other policy the backend already seeded with "*"), so a
    // brand-new policy's dropdown doesn't offer a value the catalog
    // never returns actions for.
    if (policy?.resource_type === ALL_RESOURCE_TYPES_VALUE) {
      options.unshift({
        value: ALL_RESOURCE_TYPES_VALUE,
        label: t("policies:columns.allResourceTypesTag"),
      });
    }
    return options;
  }, [catalogQuery.data, policy, t]);

  // Actions are scoped to the selected resource type: a policy grants
  // actions against one resource type, so showing every catalog action
  // regardless of selection would let an operator pick a combination no
  // route actually matches. "*" is the one exception (system_superuser):
  // it grants against every resource type, so its action list is the full
  // catalog instead of one type's slice.
  const actionOptions = useMemo(() => {
    const entries =
      resourceType === ALL_RESOURCE_TYPES_VALUE
        ? (catalogQuery.data ?? [])
        : (catalogQuery.data ?? []).filter(
            (entry) => entry.resource_type === resourceType,
          );
    const grantableEntries = entries.filter((entry) => canGrantAction(entry.action, can));
    // When editing an existing policy, retain actions already in the policy
    // so the form can display them without silently dropping state. New
    // policies never offer an action the backend's grant guard would reject.
    const visibleEntries = [
      ...grantableEntries,
      ...entries.filter((entry) => actions.includes(entry.action) && !canGrantAction(entry.action, can)),
    ];
    return visibleEntries.map((entry) => ({
      value: entry.action,
      label: entry.description?.trim() || formatPolicyActionLabel(entry.action),
    }));
  }, [actions, can, catalogQuery.data, resourceType]);

  // Snapshot of every field right after the dialog last opened, compared
  // against current values to detect unsaved edits before a close discards
  // them.
  const [initialSnapshot, setInitialSnapshot] = useState("");

  // Reset the form to the policy being edited (or blank, for create) each
  // time the dialog opens. Done during render, React's documented pattern
  // for state derived from props, since setState-in-effect costs an extra
  // render.
  // Start closed so an embedded editor that mounts directly into an already
  // open details dialog still performs the same first-open initialization as
  // the standalone create dialog.
  const [prevIsOpen, setPrevIsOpen] = useState(false);
  if (isOpen && !prevIsOpen) {
    setPrevIsOpen(isOpen);
    const initialName = policy?.name ?? "";
    const initialDescription = policy?.description ?? "";
    const initialActions = policy ? policy.actions : [];
    const initialResourceType = policy?.resource_type ?? "";
    const initialConditionsText = policy?.conditions
      ? JSON.stringify(policy.conditions, null, 2)
      : "";

    setTab("basics");
    setName(initialName);
    setDescription(initialDescription);
    setActions(initialActions);
    setResourceType(initialResourceType);
    setConditionsEnabled(!!policy?.conditions);
    setConditionsText(initialConditionsText);
    setInitialSnapshot(
      JSON.stringify([
        initialName,
        initialDescription,
        initialActions,
        initialResourceType,
        initialConditionsText,
      ]),
    );
  } else if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
  }

  const isDirty =
    JSON.stringify([
      name,
      description,
      actions,
      resourceType,
      conditionsText,
    ]) !== initialSnapshot;

  // A themed ConfirmDialog, not window.confirm, which is an unstyled
  // native dialog, the only one in an otherwise fully themed app.
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const handleActionsChange = (nextActions: string[]) => {
    const previousActions = actions;
    const previousSnapshot = initialSnapshot;
    const nextSnapshot = JSON.stringify([name, description, nextActions, resourceType, conditionsText]);
    setActions(nextActions);
    setInitialSnapshot(nextSnapshot);
    onActionsChange?.(nextActions, () => {
      setActions(previousActions);
      setInitialSnapshot(previousSnapshot);
    }, previousActions, () => {
      setActions(nextActions);
      setInitialSnapshot(nextSnapshot);
    });
  };

  // Changing resource type invalidates any selected actions that don't
  // apply to the new one, since actionOptions only offers actions scoped
  // to the current resourceType. Without this, stale selections from the
  // old type would linger in state, unreachable in the UI but still
  // submitted. Actions that are still valid for the new type (e.g. moving
  // to "*", which contains everything) are kept, not blanket-cleared -
  // this used to always reset to [], which broke editing system_superuser
  // (its resource_type is "*", so every existing action was wiped the
  // instant the dialog opened and its resourceType state was set). A 6s
  // Undo toast covers the case where something genuinely gets cleared,
  // instead of the old silent clear.
  const handleResourceTypeChange = (value: string) => {
    const validForNewType = new Set(
      (catalogQuery.data ?? [])
        .filter(
          (entry) =>
            value === ALL_RESOURCE_TYPES_VALUE || entry.resource_type === value,
        )
        .map((entry) => entry.action),
    );
    const kept = actions.filter((a) => validForNewType.has(a));
    const clearedCount = actions.length - kept.length;
    const previousActions = actions;
    const previousResourceType = resourceType;
    setResourceType(value);
    setActions(kept);
    if (clearedCount > 0) {
      toaster.create({
        title: t("policies:formDialog.clearedActionsToast", {
          count: clearedCount,
        }),
        type: "info",
        duration: 6000,
        action: {
          label: t("policies:page.undo"),
          onClick: () => {
            setResourceType(previousResourceType);
            setActions(previousActions);
          },
        },
      });
    }
  };

  const [pendingExit, setPendingExit] = useState<(() => void) | null>(null);

  const requestExit = (exit: () => void) => {
    if (isDirty) {
      setPendingExit(() => exit);
      setShowDiscardConfirm(true);
      return;
    }
    exit();
  };

  const requestClose = () => requestExit(onClose);
  const requestDetails = () => requestExit(onDetails ?? onClose);

  const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (conditionsError) {
      setTab("basics");
      return;
    }

    let conditions: Record<string, unknown> | undefined;
    if (conditionsEnabled && conditionsText.trim()) {
      conditions = JSON.parse(conditionsText) as Record<string, unknown>;
    }

    onSubmit({
      name,
      description,
      actions,
      resource_type: resourceType,
      conditions,
    });
  };

  const destructiveSelectedCount = actions.filter(isDestructiveAction).length;
  const canSave =
    !!name.trim() && !!resourceType && actions.length > 0 && !conditionsError;
  // design/policies.html's #saveSummary: a plain-language recap of what
  // Save is about to do, shown next to the buttons instead of only inside
  // the Actions tab's own counts.
  const saveSummary =
    !resourceType || actions.length === 0
      ? t("policies:formDialog.saveSummaryIncomplete")
      : destructiveSelectedCount > 0
        ? t("policies:formDialog.saveSummaryWithDestructive", {
            count: actions.length,
            destructiveCount: destructiveSelectedCount,
          })
        : t("policies:formDialog.saveSummary", { count: actions.length });

  return {
    t,
    tab,
    setTab,
    name,
    setName,
    description,
    setDescription,
    actions,
    resourceType,
    conditionsEnabled,
    setConditionsEnabled,
    conditionsText,
    setConditionsText,
    conditionsError,
    resourceTypeOptions,
    actionOptions,
    handleActionsChange,
    handleResourceTypeChange,
    requestClose,
    requestDetails,
    handleSubmit,
    destructiveSelectedCount,
    canSave,
    saveSummary,
    showDiscardConfirm,
    setShowDiscardConfirm,
    pendingExit,
    setPendingExit,
  };
}
