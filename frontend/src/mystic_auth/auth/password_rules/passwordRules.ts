/**
 * Result of testing a password against each individual security rule.
 */
export interface PasswordRules {
    lengthRule: boolean;
    upperRule: boolean;
    lowerRule: boolean;
    numberRule: boolean;
}

export type PasswordStrength = "Weak" | "Medium" | "Strong" | "";

/**
 * These must mirror password_service.validate_password_strength on the
 * backend exactly (length >= 8, upper, lower, digit; no special-char
 * requirement). A previous version checked for a special character
 * instead of a lowercase letter, so a password like "PASSWORD1!" showed
 * "Strong" and passed every client-side check here, then got rejected
 * by the backend for missing a lowercase letter, confusing UX from two
 * validation layers enforcing different rules. Shared here so
 * SignupForm and PasswordResetConfirmForm can't drift apart again.
 */
export function checkPasswordRules(pwd: string): PasswordRules {
    return {
        lengthRule: pwd.length >= 8,
        upperRule: /[A-Z]/.test(pwd),
        lowerRule: /[a-z]/.test(pwd),
        numberRule: /[0-9]/.test(pwd),
    };
}

export function evaluatePasswordStrength(pwd: string): PasswordStrength {
    if (!pwd) return "";
    const { lengthRule, upperRule, lowerRule, numberRule } = checkPasswordRules(pwd);
    const passedRules = [lengthRule, upperRule, lowerRule, numberRule].filter(Boolean).length;
    if (passedRules <= 2) return "Weak";
    if (passedRules === 3) return "Medium";
    return "Strong";
}

/**
 * `t` is threaded in (rather than this module calling useTranslation itself,
 * which it can't - it's a plain function, not a component/hook) so callers
 * reuse their own already-scoped translator. Keys are namespace-qualified
 * ("auth:...") rather than bare, since callers outside the auth/ folder
 * (e.g. account_settings/ChangePasswordCard.tsx) pass a `t` scoped to their
 * own namespace, not "auth".
 */
export function validatePassword(pwd: string, t: (key: string) => string): string | null {
    const { lengthRule, upperRule, lowerRule, numberRule } = checkPasswordRules(pwd);
    if (!lengthRule) return t("auth:passwordRules.lengthError");
    if (!upperRule) return t("auth:passwordRules.upperError");
    if (!lowerRule) return t("auth:passwordRules.lowerError");
    if (!numberRule) return t("auth:passwordRules.numberError");
    return null;
}
