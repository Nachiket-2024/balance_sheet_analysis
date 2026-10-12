import React from "react";
import { useTranslation } from "react-i18next";

import type { PasswordRules } from "./passwordRules";
import PasswordRuleItem from "./PasswordRuleItem";

interface PasswordRulesChecklistProps {
    rules: PasswordRules;
    fontSize?: string;
    /**
     * True before the user has typed anything. An empty password trivially fails
     * every rule, so rendering four red X's on first paint would read as an alarm
     * rather than guidance. Pristine shows a neutral state instead; the first
     * keystroke switches it to the normal red/green checklist.
     */
    pristine?: boolean;
    /** Tailwind grid-cols classes, e.g. "grid-cols-1 sm:grid-cols-2" so
     * PasswordStrengthPanel's checklist drops to one column below ~400px
     * (design.md's narrow-width rule for the auth pages opened from email
     * links). "grid-cols-2" (default) for a standalone, full-width
     * checklist (e.g. ChangePasswordCard). */
    columnsClassName?: string;
}

/**
 * Shared pass/fail checklist for SignupForm, PasswordResetConfirmForm, and
 * PasswordStrengthPanel. Wrapped in aria-live="polite" so screen readers announce
 * each rule's status as it changes, not just the icon color.
 *
 * Laid out as a `SimpleGrid` with equal-width columns rather than `HStack` rows: an
 * HStack row only takes the width its content needs, so longer translated labels
 * would overflow past the card's edge instead of wrapping. The grid gives each item a
 * fixed column to wrap within.
 */
const FONT_SIZE_CLASSES: Record<string, string> = { xs: "text-xs", sm: "text-sm", md: "text-base", lg: "text-lg" };

const PasswordRulesChecklist: React.FC<PasswordRulesChecklistProps> = ({ rules, fontSize = "md", pristine = false, columnsClassName = "grid-cols-2" }) => {
    const { t } = useTranslation("auth");

    return (
        <div className={`${FONT_SIZE_CLASSES[fontSize] ?? fontSize} text-fg-muted`} aria-live="polite">
            <div className={`grid ${columnsClassName} gap-x-4 gap-y-1`}>
                <PasswordRuleItem passed={rules.lengthRule} label={t("passwordRules.minLength")} pristine={pristine} />
                <PasswordRuleItem passed={rules.upperRule} label={t("passwordRules.upper")} pristine={pristine} />
                <PasswordRuleItem passed={rules.lowerRule} label={t("passwordRules.lower")} pristine={pristine} />
                <PasswordRuleItem passed={rules.numberRule} label={t("passwordRules.number")} pristine={pristine} />
            </div>
        </div>
    );
};

export default PasswordRulesChecklist;
