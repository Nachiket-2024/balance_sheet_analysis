import React from "react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";
import { DialogFooter } from "../../ui/shadcn/dialog";
import { DIALOG_FOOTER_CLASSNAME } from "../../ui/styles/dialogStyles";

interface PolicyFormDialogFooterProps {
  saveSummary: string;
  isSaving: boolean;
  canSave: boolean;
  isEditing: boolean;
  showSave: boolean;
  onClose: () => void;
}

const PolicyFormDialogFooter: React.FC<PolicyFormDialogFooterProps> = ({ saveSummary, isSaving, canSave, isEditing, showSave, onClose }) => {
  const { t } = useTranslation("policies");
  return (
    <DialogFooter className={DIALOG_FOOTER_CLASSNAME}>
      {showSave && <p className="text-sm text-fg-muted me-auto">{saveSummary}</p>}
      <Button onClick={onClose} disabled={isSaving} variant="secondary">{t("ui_text:close")}</Button>
      {showSave && <Button type="submit" form="policy-form" variant="brand" loading={isSaving} disabled={!canSave}>
        {isEditing ? t("formDialog.saveChanges") : t("formDialog.createPolicy")}
      </Button>}
    </DialogFooter>
  );
};

export default PolicyFormDialogFooter;
