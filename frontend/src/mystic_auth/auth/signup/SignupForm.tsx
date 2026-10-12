import React, { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { MailCheck, AlertCircle } from "lucide-react";

import { useSignupMutation } from "./useSignupMutation";
import FormAlert from "../../ui/feedback/FormAlert";
import PasswordInput from "../../ui/inputs/PasswordInput";
import AuthResultPanel from "../../ui/feedback/AuthResultPanel";
import { Button } from "../../ui/buttons/Button";
import { Input } from "../../ui/inputs/Input";
import { Label } from "../../ui/shadcn/label";

// Shared password policy logic and checklist UI, kept identical to PasswordResetConfirmForm.
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../password_rules/passwordRules";
import PasswordStrengthPanel from "../password_rules/PasswordStrengthPanel";
import VerificationEmailRequestForm from "../verify_account/VerificationEmailRequestForm";

interface SignupFieldErrors {
    name?: string;
    email?: string;
}

const SignupForm: React.FC = () => {
    const { t } = useTranslation("auth");
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [mismatch, setMismatch] = useState(false);
    const [passwordInvalid, setPasswordInvalid] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState<"Weak" | "Medium" | "Strong" | "">("");
    const [fieldErrors, setFieldErrors] = useState<SignupFieldErrors>({});
    const nameInputRef = useRef<HTMLInputElement>(null);
    const emailInputRef = useRef<HTMLInputElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);

    const signupMutation = useSignupMutation();

    const handlePasswordChange = (value: string) => {
        setPassword(value);
        setPasswordStrength(evaluatePasswordStrength(value));
        if (passwordInvalid) setPasswordInvalid(false);
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        const nextFieldErrors: SignupFieldErrors = {};
        if (!name.trim()) nextFieldErrors.name = t("signup.nameRequired");
        if (!email.trim()) {
            nextFieldErrors.email = t("signup.emailRequired");
        } else if (emailInputRef.current && !emailInputRef.current.validity.valid) {
            nextFieldErrors.email = t("signup.emailInvalid");
        }

        setFieldErrors(nextFieldErrors);
        if (nextFieldErrors.name) {
            nameInputRef.current?.focus();
            return;
        }
        if (nextFieldErrors.email) {
            emailInputRef.current?.focus();
            return;
        }

        // U3: the checklist below the field already shows exactly which rules
        // are failing, so a submit doesn't repeat that as prose in an alert -
        // it just flags the field and moves focus there.
        if (validatePassword(password, t)) {
            setPasswordInvalid(true);
            setMismatch(false);
            passwordInputRef.current?.focus();
            return;
        }

        if (password !== confirmPassword) {
            setMismatch(true);
            setPasswordInvalid(false);
            document.getElementById("signup-confirm-password")?.focus();
            return;
        }

        setMismatch(false);
        setPasswordInvalid(false);
        signupMutation.mutate(
            { name, email, password },
            {
                // Clears sensitive fields only (name/email stay as a receipt of what
                // was submitted); the result panel below replaces the form entirely
                // once this succeeds, so nothing here stays editable or clickable.
                onSuccess: () => {
                    setPassword("");
                    setConfirmPassword("");
                    setPasswordStrength("");
                },
            }
        );
    };

    const rules = checkPasswordRules(password);

    if (signupMutation.isSuccess) {
        return (
            <AuthResultPanel
                icon={<MailCheck size={26} />}
                variant="brand"
                title={t("signup.successTitle")}
                description={t("signup.successDescription", { email })}
            >
                <VerificationEmailRequestForm initialEmail={email} />
                <Button asChild variant="outline" size="lg" className="w-full">
                    <a href="/login">{t("signup.backToLogin")}</a>
                </Button>
            </AuthResultPanel>
        );
    }

    return (
        <form noValidate onSubmit={handleSubmit} className="w-full flex flex-col gap-3 lg:grid lg:grid-cols-2 lg:gap-x-5 lg:gap-y-3">
            <div className="flex flex-col gap-1.5">
                <Label htmlFor="signup-name" className="text-base">{t("signup.nameLabel")}</Label>
                <Input
                    id="signup-name"
                    ref={nameInputRef}
                    type="text"
                    value={name}
                    onChange={e => {
                        setName(e.target.value);
                        if (fieldErrors.name) setFieldErrors((errors) => ({ ...errors, name: undefined }));
                    }}
                    placeholder={t("signup.namePlaceholder")}
                    autoComplete="name"
                    className="bg-bg-canvas"
                    size="lg"
                    maxLength={100}
                    required
                    aria-invalid={!!fieldErrors.name}
                    aria-describedby={fieldErrors.name ? "signup-name-error" : undefined}
                />
                {fieldErrors.name && <p id="signup-name-error" className="text-sm text-fg-error flex items-center gap-1" role="alert"><AlertCircle size={14} /> {fieldErrors.name}</p>}
            </div>

            <div className="flex flex-col gap-1.5">
                <Label htmlFor="signup-email" className="text-base">{t("signup.emailLabel")}</Label>
                <Input
                    id="signup-email"
                    ref={emailInputRef}
                    type="email"
                    value={email}
                    onChange={e => {
                        setEmail(e.target.value);
                        if (fieldErrors.email) setFieldErrors((errors) => ({ ...errors, email: undefined }));
                    }}
                    placeholder={t("signup.emailPlaceholder")}
                    autoComplete="email"
                    className="bg-bg-canvas"
                    size="lg"
                    required
                    aria-invalid={!!fieldErrors.email}
                    aria-describedby={fieldErrors.email ? "signup-email-error" : undefined}
                />
                {fieldErrors.email && <p id="signup-email-error" className="text-sm text-fg-error flex items-center gap-1" role="alert"><AlertCircle size={14} /> {fieldErrors.email}</p>}
            </div>

            <div className="flex flex-col gap-1.5">
                <Label htmlFor="signup-password" className="text-base">{t("signup.passwordLabel")}</Label>
                <PasswordInput
                    id="signup-password"
                    ref={passwordInputRef}
                    value={password}
                    onChange={e => handlePasswordChange(e.target.value)}
                    placeholder={t("signup.passwordPlaceholder")}
                    autoComplete="new-password"
                    className="bg-bg-canvas"
                    size="lg"
                    aria-invalid={passwordInvalid}
                    maxLength={128}
                    required
                />
            </div>

            <div className="flex flex-col gap-1.5">
                <Label htmlFor="signup-confirm-password" className="text-base">{t("signup.confirmPasswordLabel")}</Label>
                <PasswordInput
                    id="signup-confirm-password"
                    value={confirmPassword}
                    onChange={e => {
                        setConfirmPassword(e.target.value);
                        if (mismatch) setMismatch(false);
                    }}
                    placeholder={t("signup.confirmPasswordPlaceholder")}
                    autoComplete="new-password"
                    className="bg-bg-canvas"
                    size="lg"
                    aria-invalid={mismatch}
                    aria-describedby={mismatch ? "signup-mismatch-error" : undefined}
                    maxLength={128}
                    required
                />
                {mismatch && (
                    <p id="signup-mismatch-error" className="text-sm text-fg-error flex items-center gap-1 mt-1">
                        <AlertCircle size={14} /> {t("signup.passwordsDoNotMatch")}
                    </p>
                )}
            </div>

            {/* Always rendered, even before typing starts (neutral "-" placeholder),
                and spans the full form width below both password fields. */}
            <div className="lg:col-span-2">
                <PasswordStrengthPanel
                    password={password}
                    label={t("signup.strengthLabel", { strength: passwordStrength || "-" })}
                    rules={rules}
                    pristine={!password}
                    className="mt-0"
                />
            </div>

            {/* Server errors sit directly above the main button (S6), not a
                field-level message: they're about the submission, not one field. */}
            {signupMutation.isError && (
                <div className="lg:col-span-2">
                    <FormAlert status="error" id="signup-mutation-error">{signupMutation.error.message}</FormAlert>
                </div>
            )}

            <Button
                type="submit"
                variant="brand"
                size="lg"
                className="w-full lg:col-span-2"
                loading={signupMutation.isPending}
            >
                {t("signup.submitButton")}
            </Button>
        </form>
    );
};

export default SignupForm;
