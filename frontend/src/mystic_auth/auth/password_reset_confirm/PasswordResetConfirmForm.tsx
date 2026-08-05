import React, { useState } from "react";
import { Stack, Input, Button, Text } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { usePasswordResetConfirmMutation } from "./usePasswordResetConfirmMutation";
import FormAlert from "../../ui/FormAlert";
import { BRAND_SOLID_HOVER_PROPS } from "../../ui/styles/buttonStyles";

// Shared password policy logic and checklist UI: kept identical to
// SignupForm so the two flows can't drift apart again.
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../password_rules/passwordRules";
import PasswordRulesChecklist from "../password_rules/PasswordRulesChecklist";

interface PasswordResetConfirmFormProps {
    token: string;
}

const PasswordResetConfirmForm: React.FC<PasswordResetConfirmFormProps> = ({ token: propToken }) => {
    // Token typed into the manual-entry field, used only when no token was
    // supplied via the URL. `token` derives from whichever source applies
    // instead of syncing propToken into state via an effect.
    const [manualToken, setManualToken] = useState("");
    const token = propToken || manualToken;
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [localError, setLocalError] = useState("");
    const [passwordStrength, setPasswordStrength] = useState<"Weak" | "Medium" | "Strong" | "">("");

    const resetConfirmMutation = usePasswordResetConfirmMutation();

    const handlePasswordChange = (value: string) => {
        setNewPassword(value);
        setPasswordStrength(evaluatePasswordStrength(value));
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        const passwordError = validatePassword(newPassword);
        if (passwordError) {
            setLocalError(passwordError);
            return;
        }

        if (newPassword !== confirmPassword) {
            setLocalError("Passwords do not match");
            return;
        }

        setLocalError("");
        resetConfirmMutation.mutate({ token, new_password: newPassword });
    };

    const hasTokenFromUrl = !!propToken;
    const rules = checkPasswordRules(newPassword);
    const passwordErrorId = localError
        ? "password-reset-confirm-local-error"
        : resetConfirmMutation.isError
            ? "password-reset-confirm-mutation-error"
            : undefined;

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full" gap={4}>
            {!hasTokenFromUrl && (
                <ChakraField.Root required>
                    <ChakraField.Label>Reset token</ChakraField.Label>
                    <Input
                        type="text"
                        value={token}
                        onChange={(e) => setManualToken(e.target.value)}
                        placeholder="Token from email"
                        size="lg"
                        autoFocus
                    />
                </ChakraField.Root>
            )}

            <ChakraField.Root required>
                <ChakraField.Label>New password</ChakraField.Label>
                <Input
                    type="password"
                    value={newPassword}
                    onChange={(e) => handlePasswordChange(e.target.value)}
                    placeholder="New Password"
                    size="lg"
                    autoFocus={hasTokenFromUrl}
                    aria-invalid={!!localError || resetConfirmMutation.isError}
                    aria-describedby={passwordErrorId}
                />
            </ChakraField.Root>

            {/* Always rendered, even before typing starts (showing a
                neutral "-" placeholder): kept identical to SignupForm so
                the strength label filling in never shifts the fields
                below it. */}
            <Text
                fontSize="15px"
                fontWeight="bold"
                color={
                    passwordStrength === "Weak" ? "red.500" :
                    passwordStrength === "Medium" ? "orange.400" :
                    passwordStrength === "Strong" ? "green.500" : "fg.muted"
                }
            >
                Strength: {passwordStrength || "-"}
            </Text>

            <PasswordRulesChecklist rules={rules} fontSize="15px" />

            <ChakraField.Root required>
                <ChakraField.Label>Confirm new password</ChakraField.Label>
                <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm New Password"
                    size="lg"
                    aria-invalid={!!localError}
                    aria-describedby={localError ? "password-reset-confirm-local-error" : undefined}
                />
            </ChakraField.Root>

            <Button
                type="submit"
                colorPalette="brand"
                size="lg"
                w="full"
                loading={resetConfirmMutation.isPending}
                loadingText="Resetting..."
                {...BRAND_SOLID_HOVER_PROPS}
            >
                Reset Password
            </Button>

            {localError && <FormAlert status="error" id="password-reset-confirm-local-error">{localError}</FormAlert>}

            {resetConfirmMutation.isError && (
                <FormAlert status="error" id="password-reset-confirm-mutation-error">{resetConfirmMutation.error.message}</FormAlert>
            )}

            {resetConfirmMutation.isSuccess && (
                <FormAlert status="success">{resetConfirmMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default PasswordResetConfirmForm;
