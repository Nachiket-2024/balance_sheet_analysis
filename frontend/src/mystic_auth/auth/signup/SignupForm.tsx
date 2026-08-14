import React, { useState } from "react";
import { Stack, Input, Button, Text } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";

import { useSignupMutation } from "./useSignupMutation";
import FormAlert from "../../ui/FormAlert";
import { BRAND_SOLID_HOVER_PROPS } from "../../ui/styles/buttonStyles";

// Shared password policy logic and checklist UI, kept identical to
// PasswordResetConfirmForm so the two flows can't drift apart again.
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../password_rules/passwordRules";
import PasswordRulesChecklist from "../password_rules/PasswordRulesChecklist";

const SignupForm: React.FC = () => {
    const { t } = useTranslation("auth");
    const [name, setName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [localError, setLocalError] = useState("");
    const [passwordStrength, setPasswordStrength] = useState<"Weak" | "Medium" | "Strong" | "">("");

    const signupMutation = useSignupMutation();

    const handlePasswordChange = (value: string) => {
        setPassword(value);
        setPasswordStrength(evaluatePasswordStrength(value));
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        const passwordError = validatePassword(password, t);
        if (passwordError) {
            setLocalError(passwordError);
            return;
        }

        if (password !== confirmPassword) {
            setLocalError(t("signup.passwordsDoNotMatch"));
            return;
        }

        setLocalError("");
        signupMutation.mutate(
            { name, email, password },
            {
                // Clears the sensitive fields (not name/email, which stay
                // as a visible receipt of what was submitted) and, with the
                // button below, blocks an accidental duplicate submit with
                // the same still-filled password once signup has already
                // succeeded.
                onSuccess: () => {
                    setPassword("");
                    setConfirmPassword("");
                    setPasswordStrength("");
                },
            }
        );
    };

    const rules = checkPasswordRules(password);
    const passwordErrorId = localError ? "signup-password-error" : signupMutation.isError ? "signup-mutation-error" : undefined;

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full">
            <Stack direction="row">
                <ChakraField.Root required flex={1}>
                    <ChakraField.Label>{t("signup.nameLabel")}</ChakraField.Label>
                    <Input
                        type="text"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        placeholder={t("signup.namePlaceholder")}
                    />
                </ChakraField.Root>

                <ChakraField.Root required flex={1}>
                    <ChakraField.Label>{t("signup.emailLabel")}</ChakraField.Label>
                    <Input
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder={t("signup.emailPlaceholder")}
                    />
                </ChakraField.Root>
            </Stack>

            <ChakraField.Root required>
                <ChakraField.Label>{t("signup.passwordLabel")}</ChakraField.Label>
                <Input
                    type="password"
                    value={password}
                    onChange={e => handlePasswordChange(e.target.value)}
                    placeholder={t("signup.passwordPlaceholder")}
                    aria-invalid={!!localError || signupMutation.isError}
                    aria-describedby={passwordErrorId}
                />
                {/* Always rendered, even before typing starts (showing a
                    neutral "-" placeholder): reserving this line's height
                    from the very first render means the strength label
                    filling in never shifts the fields below it, unlike a
                    conditionally-mounted line that only appears once
                    passwordStrength has a value. */}
                <Text
                    mt={1}
                    fontSize="15px"
                    fontWeight="bold"
                    color={
                        passwordStrength === "Weak" ? "red.500" :
                        passwordStrength === "Medium" ? "orange.400" :
                        passwordStrength === "Strong" ? "green.500" : "fg.muted"
                    }
                >
                    {t("signup.strengthLabel", { strength: passwordStrength || "-" })}
                </Text>
            </ChakraField.Root>

            <PasswordRulesChecklist rules={rules} fontSize="15px" />

            <ChakraField.Root required>
                <ChakraField.Label>{t("signup.confirmPasswordLabel")}</ChakraField.Label>
                <Input
                    type="password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder={t("signup.confirmPasswordPlaceholder")}
                    aria-invalid={!!localError}
                    aria-describedby={localError ? "signup-password-error" : undefined}
                />
            </ChakraField.Root>

            {localError && <FormAlert status="error" id="signup-password-error">{localError}</FormAlert>}
            {signupMutation.isError && (
                <FormAlert status="error" id="signup-mutation-error">{signupMutation.error.message}</FormAlert>
            )}
            {signupMutation.isSuccess && (
                <FormAlert status="success">{signupMutation.data.message}</FormAlert>
            )}

            {/* Signup shows a spinner and disables itself while the request
                is in flight, preventing double-submit. */}
            <Button
                type="submit"
                colorPalette="brand"
                w="full"
                fontSize="md"
                loading={signupMutation.isPending}
                loadingText={t("signup.signingUp")}
                disabled={signupMutation.isSuccess}
                {...BRAND_SOLID_HOVER_PROPS}
            >
                {t("signup.submitButton")}
            </Button>

            {/* Matches LoginPage's reciprocal "Don't have an account? Sign
                Up" treatment - a plain inline link, not a second competing
                button, so the two auth pages read as one consistent
                pattern instead of two different conventions for the same
                "wrong page? go to the other one" action. */}
            <Text fontSize="16px" color="fg.muted" textAlign="center">
                {t("signup.alreadyHaveAccount")}{" "}
                <Link to="/login" style={{ color: "var(--chakra-colors-brand-fg)", fontWeight: 600 }}>
                    {t("signup.login")}
                </Link>
            </Text>
        </Stack>
    );
};

export default SignupForm;
