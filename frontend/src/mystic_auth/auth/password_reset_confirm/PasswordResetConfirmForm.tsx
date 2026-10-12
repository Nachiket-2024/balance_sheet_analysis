import React, { useRef, useState } from "react";
import axios from "axios";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Link2Off, AlertCircle } from "lucide-react";
import { Link } from "react-router";

import { usePasswordResetConfirmMutation } from "./usePasswordResetConfirmMutation";
import FormAlert from "../../ui/feedback/FormAlert";
import PasswordInput from "../../ui/inputs/PasswordInput";
import AuthResultPanel from "../../ui/feedback/AuthResultPanel";
import AuthInlineLink from "../../ui/links/AuthInlineLink";
import { Button } from "../../ui/buttons/Button";
import { Input } from "../../ui/inputs/Input";
import { Label } from "../../ui/shadcn/label";

// Shared password policy logic and checklist UI, kept identical to SignupForm.
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../password_rules/passwordRules";
import PasswordStrengthPanel from "../password_rules/PasswordStrengthPanel";

interface PasswordResetConfirmFormProps {
    token: string;
}

// Reserve the dedicated expired-link panel for the backend's explicit token
// failure. INVALID_RESET_TOKEN_OR_PASSWORD can also mean a valid link paired
// with a rejected password, so it must remain an actionable form error.
function isDeadResetLinkError(error: Error): boolean {
    const cause = error.cause;
    if (!axios.isAxiosError(cause)) return false;
    const code = cause.response?.data?.code;
    return code === "INVALID_OR_EXPIRED_RESET_TOKEN";
}

const PasswordResetConfirmForm: React.FC<PasswordResetConfirmFormProps> = ({ token: propToken }) => {
    const { t } = useTranslation("auth");
    // Manual-entry fallback, used only when no token came from the URL. `token`
    // derives from whichever source applies instead of syncing propToken via an effect.
    const [manualToken, setManualToken] = useState("");
    const token = propToken || manualToken;
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [mismatch, setMismatch] = useState(false);
    const [passwordInvalid, setPasswordInvalid] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState<"Weak" | "Medium" | "Strong" | "">("");
    const passwordInputRef = useRef<HTMLInputElement>(null);

    const resetConfirmMutation = usePasswordResetConfirmMutation();

    const handlePasswordChange = (value: string) => {
        setNewPassword(value);
        setPasswordStrength(evaluatePasswordStrength(value));
        if (passwordInvalid) setPasswordInvalid(false);
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        // U3's fix, reused here too (R1): a failing rule flags the field and
        // moves focus there instead of repeating it as prose in an alert -
        // the checklist below already shows it live.
        if (validatePassword(newPassword, t)) {
            setPasswordInvalid(true);
            setMismatch(false);
            passwordInputRef.current?.focus();
            return;
        }

        if (newPassword !== confirmPassword) {
            setMismatch(true);
            setPasswordInvalid(false);
            return;
        }

        setMismatch(false);
        setPasswordInvalid(false);
        resetConfirmMutation.mutate(
            { token, new_password: newPassword },
            {
                // Same "clear the sensitive fields, disable the button" treatment
                // as SignupForm.tsx: without this, the new password stayed
                // filled in and submittable again after a successful reset.
                onSuccess: () => {
                    setNewPassword("");
                    setConfirmPassword("");
                    setPasswordStrength("");
                },
            }
        );
    };

    const hasTokenFromUrl = !!propToken;
    const rules = checkPasswordRules(newPassword);

    // R2: success replaces the form with a result panel instead of leaving
    // the filled-in form visible and re-clickable.
    if (resetConfirmMutation.isSuccess) {
        const sessionsRevoked = resetConfirmMutation.data.sessions_revoked !== false;
        return (
            <AuthResultPanel
                icon={<CheckCircle2 size={26} />}
                variant="success"
                title={t("passwordResetConfirm.successTitle")}
                description={sessionsRevoked
                    ? t("passwordResetConfirm.loggedOutOtherDevices")
                    : t("passwordResetConfirm.resetButSessionsNotRevoked")}
            >
                <Button asChild variant="brand" size="lg" className="w-full">
                    <Link to="/login">{t("passwordResetConfirmPage.backToLogin")}</Link>
                </Button>
            </AuthResultPanel>
        );
    }

    // A confirmed dead link can only fail the same way again, so a failed
    // submit against it swaps straight to "here's what to do next". Other
    // reset failures keep the form available for correction or retry.
    if (resetConfirmMutation.isError && isDeadResetLinkError(resetConfirmMutation.error)) {
        return (
            <AuthResultPanel
                icon={<Link2Off size={26} />}
                variant="error"
                title={t("passwordResetConfirm.linkExpiredTitle")}
                description={t("passwordResetConfirm.linkExpiredDescription")}
            >
                <Button asChild variant="brand" size="lg" className="w-full">
                    <Link to="/password-reset-request">{t("passwordResetConfirm.requestNewLink")}</Link>
                </Button>
            </AuthResultPanel>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
            {!hasTokenFromUrl && (
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="password-reset-confirm-token" className="text-base">{t("passwordResetConfirm.resetTokenLabel")}</Label>
                    <Input
                        id="password-reset-confirm-token"
                        type="text"
                        value={token}
                        onChange={(e) => setManualToken(e.target.value)}
                        placeholder={t("passwordResetConfirm.resetTokenPlaceholder")}
                        className="bg-bg-canvas"
                        size="lg"
                        autoFocus
                    />
                    <p className="text-sm text-fg-muted">{t("passwordResetConfirm.resetTokenHint")}</p>
                </div>
            )}

            <div className="flex flex-col gap-1.5">
                <Label htmlFor="password-reset-confirm-new-password" className="text-base">{t("passwordResetConfirm.newPasswordLabel")}</Label>
                <PasswordInput
                    id="password-reset-confirm-new-password"
                    ref={passwordInputRef}
                    value={newPassword}
                    onChange={(e) => handlePasswordChange(e.target.value)}
                    placeholder={t("passwordResetConfirm.newPasswordPlaceholder")}
                    autoComplete="new-password"
                    className="bg-bg-canvas"
                    size="lg"
                    autoFocus={hasTokenFromUrl}
                    aria-invalid={passwordInvalid}
                    maxLength={128}
                />
                {/* Always rendered, even before typing starts (neutral "-" placeholder), so
                    the strength meter filling in never shifts the fields below it. */}
                <PasswordStrengthPanel
                    password={newPassword}
                    label={t("passwordResetConfirm.strengthLabel", { strength: passwordStrength || "-" })}
                    rules={rules}
                    pristine={!newPassword}
                    className="mt-2"
                />
            </div>

            <div className="flex flex-col gap-1.5">
                <Label htmlFor="password-reset-confirm-confirm-password" className="text-base">{t("passwordResetConfirm.confirmNewPasswordLabel")}</Label>
                <PasswordInput
                    id="password-reset-confirm-confirm-password"
                    value={confirmPassword}
                    onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (mismatch) setMismatch(false);
                    }}
                    placeholder={t("passwordResetConfirm.confirmNewPasswordPlaceholder")}
                    autoComplete="new-password"
                    className="bg-bg-canvas"
                    size="lg"
                    aria-invalid={mismatch}
                    aria-describedby={mismatch ? "reset-confirm-mismatch-error" : undefined}
                    maxLength={128}
                />
                {mismatch && (
                    <p id="reset-confirm-mismatch-error" className="text-sm text-fg-error flex items-center gap-1 mt-1">
                        <AlertCircle size={14} /> {t("passwordResetConfirm.passwordsDoNotMatch")}
                    </p>
                )}
            </div>

            {/* Server errors sit directly above the main button (S6). A dead
                link/code short-circuits to the result panel above instead of
                landing here. */}
            {resetConfirmMutation.isError && (
                <FormAlert status="error">{resetConfirmMutation.error.message}</FormAlert>
            )}

            <Button
                type="submit"
                variant="brand"
                size="lg"
                className="w-full"
                loading={resetConfirmMutation.isPending}
            >
                {t("passwordResetConfirm.submitButton")}
            </Button>

            <p className="text-sm text-fg-muted text-center">
                {t("loginPage.agreeToTermsPrefix")}{" "}
                <AuthInlineLink to="/terms">{t("loginPage.termsOfService")}</AuthInlineLink>{" "}
                {t("loginPage.and")}{" "}
                <AuthInlineLink to="/privacy">{t("loginPage.privacyPolicy")}</AuthInlineLink>
            </p>

            <p className="text-base text-fg-muted text-center">
                {t("passwordResetConfirmPage.rememberPassword")}{" "}
                <AuthInlineLink to="/login">{t("passwordResetConfirmPage.backToLogin")}</AuthInlineLink>
            </p>
        </form>
    );
};

export default PasswordResetConfirmForm;
