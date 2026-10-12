// Result of testing a password against each individual security rule.
export interface PasswordRules {
    lengthRule: boolean;
    upperRule: boolean;
    lowerRule: boolean;
    numberRule: boolean;
}

export type PasswordStrength = "Weak" | "Medium" | "Strong" | "";

// Must mirror password_service.validate_password_strength on the backend exactly
// (length >= 8, upper, lower, digit; no special-char requirement). A previous version
// checked for a special character instead of a lowercase letter, so e.g. "PASSWORD1!"
// showed "Strong" here but got rejected by the backend. Shared so SignupForm and
// PasswordResetConfirmForm can't drift apart again.
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

// `t` is threaded in (this is a plain function, not a component/hook, so it can't call
// useTranslation itself) so callers reuse their own scoped translator. Keys are
// namespace-qualified ("auth:...") since callers outside auth/ (e.g.
// account_settings/ChangePasswordCard.tsx) pass a `t` scoped to their own namespace.
export function validatePassword(pwd: string, t: (key: string) => string): string | null {
    const { lengthRule, upperRule, lowerRule, numberRule } = checkPasswordRules(pwd);
    if (!lengthRule) return t("auth:passwordRules.lengthError");
    if (!upperRule) return t("auth:passwordRules.upperError");
    if (!lowerRule) return t("auth:passwordRules.lowerError");
    if (!numberRule) return t("auth:passwordRules.numberError");
    return null;
}
