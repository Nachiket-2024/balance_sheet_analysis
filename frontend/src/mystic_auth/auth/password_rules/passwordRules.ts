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

export function validatePassword(pwd: string): string | null {
    const { lengthRule, upperRule, lowerRule, numberRule } = checkPasswordRules(pwd);
    if (!lengthRule) return "Password must be at least 8 characters long";
    if (!upperRule) return "Password must contain at least one uppercase letter";
    if (!lowerRule) return "Password must contain at least one lowercase letter";
    if (!numberRule) return "Password must contain at least one number";
    return null;
}
