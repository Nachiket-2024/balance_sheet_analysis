import React from "react";
import { CircleHelp } from "lucide-react";
import { useTranslation } from "react-i18next";

import FormAlert from "../../ui/feedback/FormAlert";
import StyledSelect from "../../ui/filters/StyledSelect";
import { Checkbox } from "../../ui/shadcn/checkbox";
import { Input } from "../../ui/inputs/Input";
import { Textarea } from "../../ui/inputs/Textarea";
import { Label } from "../../ui/shadcn/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../ui/shadcn/tooltip";
import { DIALOG_SECTION_CLASSNAME } from "../../ui/styles/dialogStyles";
import {
  POLICY_DESCRIPTION_MAX_LENGTH,
  POLICY_NAME_MAX_LENGTH,
} from "../policyCardHelpers";

interface PolicyFormFieldsProps {
  name: string;
  description: string;
  resourceType: string;
  resourceTypeOptions: { value: string; label: string }[];
  conditionsEnabled: boolean;
  conditionsText: string;
  conditionsError: string | null;
  errorMessage: string | null;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onResourceTypeChange: (value: string) => void;
  onConditionsEnabledChange: (value: boolean) => void;
  onConditionsTextChange: (value: string) => void;
}

const PolicyFormFields: React.FC<PolicyFormFieldsProps> = ({
  name,
  description,
  resourceType,
  resourceTypeOptions,
  conditionsEnabled,
  conditionsText,
  conditionsError,
  errorMessage,
  onNameChange,
  onDescriptionChange,
  onResourceTypeChange,
  onConditionsEnabledChange,
  onConditionsTextChange,
}) => {
  const { t } = useTranslation(["policies", "ui_text"]);
  return (
    <div className={DIALOG_SECTION_CLASSNAME}>
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="policy-form-name">
              {t("policies:formDialog.name")}
            </Label>
            <Input
              id="policy-form-name"
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
              placeholder={t("policies:formDialog.namePlaceholder")}
              maxLength={POLICY_NAME_MAX_LENGTH}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5">
              <Label>{t("policies:formDialog.resourceType")}</Label>
              <TooltipProvider delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      aria-label={t(
                        "policies:formDialog.resourceTypeHelperText",
                      )}
                      className="flex cursor-pointer items-center justify-center text-fg-muted focus-visible:outline-2 focus-visible:outline-brand-solid"
                    >
                      <CircleHelp size={14} aria-hidden="true" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64 text-center bg-bg-surface text-fg-default border border-border-default shadow-card [&>svg]:bg-bg-surface [&>svg]:fill-bg-surface">
                    {t("policies:formDialog.resourceTypeHelperText")}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <StyledSelect
              ariaLabel={t("policies:formDialog.resourceType")}
              placeholder={t("policies:formDialog.resourceTypePlaceholder")}
              value={resourceType}
              onChange={onResourceTypeChange}
              options={resourceTypeOptions}
            />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="policy-form-description">
            {t("policies:formDialog.description")}
          </Label>
          <Input
            id="policy-form-description"
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            placeholder={t("policies:formDialog.descriptionPlaceholder")}
            maxLength={POLICY_DESCRIPTION_MAX_LENGTH}
            aria-describedby="policy-form-description-help"
          />
          <div
            id="policy-form-description-help"
            className="flex items-start justify-between gap-3 text-sm text-fg-muted"
          >
            <span>{t("policies:formDialog.descriptionHelperText")}</span>
            <span className="shrink-0 tabular-nums" aria-live="polite">
              {t("policies:formDialog.descriptionCharacterCount", {
                count: description.length,
                max: POLICY_DESCRIPTION_MAX_LENGTH,
              })}
            </span>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer w-fit">
          <Checkbox
            checked={conditionsEnabled}
            onCheckedChange={(checked) => onConditionsEnabledChange(!!checked)}
          />
          {t("policies:formDialog.addConditionsToggle")}
        </label>
        {conditionsEnabled && (
          <div className="flex flex-col gap-1.5">
            <p className="text-sm text-fg-muted">
              {t("policies:formDialog.conditionsHelperText")}
            </p>
            <Textarea
              value={conditionsText}
              onChange={(event) => onConditionsTextChange(event.target.value)}
              placeholder={t("policies:formDialog.conditionsPlaceholder")}
              rows={4}
              aria-invalid={!!conditionsError}
            />
            {conditionsError && (
              <p className="text-sm text-fg-error">{conditionsError}</p>
            )}
          </div>
        )}
        {errorMessage && <FormAlert status="error">{errorMessage}</FormAlert>}
      </div>
    </div>
  );
};

export default PolicyFormFields;
