import React from "react";

import { cn } from "../../ui/styles/classNames";
import type { PasswordRules } from "./passwordRules";
import { evaluatePasswordStrength } from "./passwordRules";
import PasswordRulesChecklist from "./PasswordRulesChecklist";

interface PasswordStrengthPanelProps {
    password: string;
    /** Pre-translated "Strength: Weak"/"Strength: -" text - the exact
     * translation key differs per caller's namespace (auth vs
     * account_settings), so callers own the t() call. */
    label: string;
    rules: PasswordRules;
    pristine?: boolean;
    /** Tailwind margin-top class, e.g. "mt-2". */
    className?: string;
}

const SEGMENT_COUNT = 4;

/**
 * Strength bar + label full width above the checklist, left-aligned - not a
 * centered block with the bar off to one side (design/auth.html's signup/
 * reset states). The checklist collapses to a single column below ~400px
 * (design.md's narrow-width rule) so each rule stays on one line at 360px.
 */
// Semantic strength color, as both a bg- and text- Tailwind class (the
// segment bars need the former, the label the latter).
const STRENGTH_CLASSES: Record<string, { bg: string; text: string }> = {
    Weak: { bg: "bg-fg-error", text: "text-fg-error" },
    Medium: { bg: "bg-fg-warning", text: "text-fg-warning" },
    Strong: { bg: "bg-fg-success", text: "text-fg-success" },
};

const PasswordStrengthPanel: React.FC<PasswordStrengthPanelProps> = ({ password, label, rules, pristine, className }) => {
    const strength = evaluatePasswordStrength(password);
    const filled = Object.values(rules).filter(Boolean).length;

    const strengthClasses = STRENGTH_CLASSES[strength] ?? { bg: "bg-border-default", text: "text-border-default" };

    return (
        <div className={cn("flex flex-col w-full gap-2.5", className)}>
            <div className="flex flex-col gap-1.5">
                <p className={cn("text-sm font-semibold", strength ? strengthClasses.text : "text-fg-muted")}>
                    {label}
                </p>
                <div className="flex items-center gap-1" aria-hidden="true">
                    {Array.from({ length: SEGMENT_COUNT }).map((_, i) => (
                        <div
                            key={i}
                            className={cn(
                                "h-1 flex-1 rounded-full transition-[background-color] duration-[var(--duration-fast)] ease-[var(--easing-hover)]",
                                i < filled ? strengthClasses.bg : "bg-border-default"
                            )}
                        />
                    ))}
                </div>
            </div>

            <PasswordRulesChecklist rules={rules} pristine={pristine} columnsClassName="grid-cols-1 sm:grid-cols-2" fontSize="sm" />
        </div>
    );
};

export default PasswordStrengthPanel;
