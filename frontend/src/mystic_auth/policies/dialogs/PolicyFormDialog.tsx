import React from "react";
import { FileText, ListChecks } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { PolicyRead } from "../../api/policies_api";
import ConfirmDialog from "../../ui/feedback/ConfirmDialog";
import PolicyActionGrid from "./PolicyActionGrid";
import { Dialog, DialogContent } from "../../ui/shadcn/dialog";
import { DIALOG_PANEL_CLASSNAME } from "../../ui/styles/dialogStyles";
import PolicyFormFields from "./PolicyFormFields";
import PolicyFormDialogHeader from "./PolicyFormDialogHeader";
import PolicyFormDialogFooter from "./PolicyFormDialogFooter";
import PolicyDialogTabs from "./PolicyDialogTabs";
import SegmentedControl from "../../ui/filters/SegmentedControl";
import { usePolicyFormState } from "./usePolicyFormState";

export interface PolicyFormValues {
  name: string;
  description: string;
  actions: string[];
  resource_type: string;
  conditions?: Record<string, unknown>;
}

interface PolicyFormDialogProps {
  isOpen: boolean;
  /** Present when editing an existing policy; absent when creating. */
  policy?: PolicyRead;
  isSaving: boolean;
  errorMessage: string | null;
  onSubmit: (values: PolicyFormValues) => void;
  onActionsChange?: (
    actions: string[],
    rollback: () => void,
    previousActions: string[],
    apply: () => void,
  ) => void;
  onClose: () => void;
  onDetails?: () => void;
  embedded?: boolean;
}

/** Shared create/edit policy form with scoped actions and condition
 * validation. Form state, derived options, and edit handlers live in
 * usePolicyFormState.ts - this file is the JSX layer, split out of one
 * 402-line file, see AGENTS.md's ~350-line target. */
const PolicyFormDialog: React.FC<PolicyFormDialogProps> = ({
  isOpen,
  policy,
  isSaving,
  errorMessage,
  onSubmit,
  onActionsChange,
  onClose,
  onDetails,
  embedded = false,
}) => {
  const { t } = useTranslation(["policies", "ui_text"]);
  const {
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
    canSave,
    saveSummary,
    showDiscardConfirm,
    setShowDiscardConfirm,
    pendingExit,
    setPendingExit,
  } = usePolicyFormState({ isOpen, policy, onSubmit, onActionsChange, onClose, onDetails });

  const formPanel = (
    <>
          <div id="policy-dialog-panel-edit" role="tabpanel" aria-labelledby="policy-dialog-tab-edit" className="flex min-h-0 flex-1 flex-col overflow-hidden bg-bg-canvas">
            {policy && !embedded && <PolicyDialogTabs activeTab="edit" showEdit onDetails={requestDetails} onEdit={() => undefined} />}
            {!embedded && <PolicyFormDialogHeader isEditing={!!policy} policy={policy} />}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-5 sm:px-6">
            <div className="flex items-center justify-start bg-bg-canvas py-3">
              <SegmentedControl
                value={tab}
                onChange={(value) => setTab(value as "basics" | "actions")}
                ariaLabel={t("policies:formDialog.tabsAriaLabel")}
                className="w-full sm:w-auto"
                tabRole
                tabPanelIds={["policy-form-tabpanel-basics", "policy-form-tabpanel-actions"]}
                options={[
                  { value: "basics", label: <><FileText size={16} aria-hidden="true" />{t("policies:formDialog.tabBasics")}</> },
                  { value: "actions", label: <><ListChecks size={16} aria-hidden="true" />{t("policies:formDialog.tabActions")}<span className="min-w-5 rounded-full bg-bg-muted px-1.5 text-center text-xs text-fg-muted">{actions.length}</span></> },
                ]}
              />
            </div>
            <form id="policy-form" onSubmit={handleSubmit} className="flex-1 min-h-0 overflow-y-auto pb-3 [scrollbar-gutter:stable]">
              <div id="policy-form-tabpanel-basics" role="tabpanel" aria-labelledby="policy-form-tab-basics" className={tab === "basics" ? undefined : "hidden"}>
                  <PolicyFormFields
                    name={name}
                    description={description}
                    resourceType={resourceType}
                    resourceTypeOptions={resourceTypeOptions}
                    conditionsEnabled={conditionsEnabled}
                    conditionsText={conditionsText}
                    conditionsError={conditionsError}
                    errorMessage={errorMessage}
                    onNameChange={setName}
                    onDescriptionChange={setDescription}
                    onResourceTypeChange={handleResourceTypeChange}
                    onConditionsEnabledChange={setConditionsEnabled}
                    onConditionsTextChange={setConditionsText}
                  />
              </div>
              <div id="policy-form-tabpanel-actions" role="tabpanel" aria-labelledby="policy-form-tab-actions" className={tab === "actions" ? undefined : "hidden"}>
                  <div className="mt-4">
                    <PolicyActionGrid ariaLabel={t("policies:formDialog.actions")} values={actions} onChange={handleActionsChange} options={actionOptions} disabled={!resourceType} />
                  </div>
              </div>
            </form>
          </div>
          </div>
          <PolicyFormDialogFooter saveSummary={saveSummary} isSaving={isSaving} canSave={canSave} isEditing={!!policy} showSave={tab === "basics" || !policy} onClose={requestClose} />
    </>
  );

  return (
    <>
      {embedded ? formPanel : (
        <Dialog modal={false} open={isOpen} onOpenChange={(open) => !open && requestClose()}>
          <DialogContent
            overlayClassName="backdrop-blur-[2px]"
            closeLabel={t("ui_text:closeDialog")}
            className={`w-[calc(100vw-1.5rem)] sm:max-w-3xl lg:max-w-[55rem] h-[min(44rem,calc(100svh-1.5rem))] flex flex-col overflow-hidden ${DIALOG_PANEL_CLASSNAME}`}
          >
            {formPanel}
          </DialogContent>
        </Dialog>
      )}

      <ConfirmDialog
        isOpen={showDiscardConfirm}
        title={t("policies:formDialog.discardTitle")}
        description={t("policies:formDialog.discardDescription")}
        confirmLabel={t("policies:formDialog.discard")}
        onConfirm={() => {
          setShowDiscardConfirm(false);
          const exit = pendingExit ?? onClose;
          setPendingExit(null);
          exit();
        }}
        onCancel={() => {
          setPendingExit(null);
          setShowDiscardConfirm(false);
        }}
      />
    </>
  );
};

export default PolicyFormDialog;
