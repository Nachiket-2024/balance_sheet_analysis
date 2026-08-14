import React, { useEffect, useState } from "react";
import { Button, Field, Heading, Input, Stack, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import Card from "../ui/Card";
import FormAlert from "../ui/FormAlert";
import PasswordRulesChecklist from "../auth/password_rules/PasswordRulesChecklist";
import { useUpdateMyAccountMutation } from "./useUpdateMyAccountMutation";
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../auth/password_rules/passwordRules";
import { toaster } from "../ui/toaster/toasterInstance";
import { BRAND_SOLID_HOVER_PROPS } from "../ui/styles/buttonStyles";
import { SEARCH_INPUT_PROPS } from "../ui/styles/inputStyles";

interface ChangePasswordCardProps {
    hasPassword: boolean;
    /** Reports whether there's an in-progress (unsaved) password edit, so
     * AccountSettingsPage can combine it with the name card's own dirty
     * state for one page-level unsaved-changes warning. */
    onDirtyChange: (isDirty: boolean) => void;
}

/**
 * ChangePasswordCard
 * ----------------------------
 * The password-change half of AccountSettingsPage: its own independent
 * mutation instance (not shared with ProfileNameCard) so saving a password
 * change never shows a loading spinner or a stale error on the unrelated
 * name card, and vice versa.
 */
const ChangePasswordCard: React.FC<ChangePasswordCardProps> = ({ hasPassword, onDirtyChange }) => {
    const { t } = useTranslation("account_settings");
    const [newPassword, setNewPassword] = useState("");
    const [currentPassword, setCurrentPassword] = useState("");
    const [passwordError, setPasswordError] = useState("");

    const passwordMutation = useUpdateMyAccountMutation();

    const rules = checkPasswordRules(newPassword);
    const strength = evaluatePasswordStrength(newPassword);

    const isDirty = newPassword.length > 0;
    useEffect(() => {
        onDirtyChange(isDirty);
    }, [isDirty, onDirtyChange]);

    const handlePasswordSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        setPasswordError("");

        const validationError = validatePassword(newPassword, t);
        if (validationError) {
            setPasswordError(validationError);
            return;
        }
        // Only an account that already has a password needs to confirm it:
        // setting one for the first time on an OAuth-only account has
        // nothing to confirm against.
        if (hasPassword && !currentPassword) {
            setPasswordError(t("changePassword.confirmCurrentRequired"));
            return;
        }

        const payload: { password: string; current_password?: string } = { password: newPassword };
        if (hasPassword) payload.current_password = currentPassword;

        passwordMutation.mutate(payload, {
            onSuccess: () => {
                toaster.create({ title: t("changePassword.updatedToast"), type: "success" });
                setNewPassword("");
                setCurrentPassword("");
            },
        });
    };

    return (
        <Card p={5} flex="1 1 320px" maxW="lg">
            <Heading as="h2" size="md" mb={3}>
                {hasPassword ? t("changePassword.changeTitle") : t("changePassword.setTitle")}
            </Heading>
            <Stack as="form" onSubmit={handlePasswordSubmit} gap={4}>
                <Field.Root>
                    <Field.Label>{hasPassword ? t("changePassword.newPasswordLabel") : t("changePassword.setPasswordFieldLabel")}</Field.Label>
                    <Input
                        type="password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        placeholder={
                            hasPassword
                                ? t("changePassword.placeholderKeepCurrent")
                                : t("changePassword.placeholderAddPassword")
                        }
                        aria-invalid={!!passwordError || passwordMutation.isError}
                        aria-describedby={passwordError ? "password-local-error" : passwordMutation.isError ? "password-mutation-error" : undefined}
                        {...SEARCH_INPUT_PROPS}
                    />
                    {/* Always rendered (a neutral "-" before typing starts),
                        same reasoning as SignupForm/PasswordResetConfirmForm:
                        reserving this line's height from the first render
                        means it filling in never shifts the fields below it. */}
                    <Text
                        mt={1}
                        fontSize="sm"
                        fontWeight="bold"
                        color={
                            strength === "Weak" ? "red.500" :
                            strength === "Medium" ? "orange.400" :
                            strength === "Strong" ? "green.500" : "fg.muted"
                        }
                    >
                        {t("changePassword.strengthLabel", { strength: strength || "-" })}
                    </Text>
                </Field.Root>

                {/* Directly below New password, not after Current
                    password: these rules describe the new password
                    you're typing above, not the confirmation field
                    below, so they read more naturally attached to
                    the field they're actually validating. */}
                <PasswordRulesChecklist rules={rules} />

                {/* Always rendered when the account has a password to
                    confirm against, not only once newPassword has a
                    value: this whole card should look the same the
                    moment it opens as it does mid-edit, not visibly grow
                    a field the instant you start typing. */}
                {hasPassword && (
                    <Field.Root>
                        <Field.Label>{t("changePassword.currentPasswordLabel")}</Field.Label>
                        <Input
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            placeholder={t("changePassword.currentPasswordPlaceholder")}
                            aria-invalid={!!passwordError}
                            aria-describedby={passwordError ? "password-local-error" : undefined}
                            {...SEARCH_INPUT_PROPS}
                        />
                    </Field.Root>
                )}

                {passwordError && <FormAlert status="error" id="password-local-error">{passwordError}</FormAlert>}
                {passwordMutation.isError && <FormAlert status="error" id="password-mutation-error">{passwordMutation.error.message}</FormAlert>}

                <Button
                    type="submit"
                    colorPalette="brand"
                    alignSelf="flex-start"
                    loading={passwordMutation.isPending}
                    loadingText={t("ui_text:saving")}
                    {...BRAND_SOLID_HOVER_PROPS}
                >
                    {hasPassword ? t("changePassword.updateButton") : t("changePassword.setButton")}
                </Button>
            </Stack>
        </Card>
    );
};

export default ChangePasswordCard;
