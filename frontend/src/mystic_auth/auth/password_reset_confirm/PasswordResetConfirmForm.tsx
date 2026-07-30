import React, { useState } from "react";
import { Stack, Input, Button, Text } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { usePasswordResetConfirmMutation } from "./usePasswordResetConfirmMutation";
import FormAlert from "../../ui/FormAlert";

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

    const handleClear = () => {
        resetConfirmMutation.reset();
        if (!propToken) {
            setManualToken("");
        }
        setNewPassword("");
        setConfirmPassword("");
        setLocalError("");
        setPasswordStrength("");
    };

    const hasTokenFromUrl = !!propToken;
    const rules = checkPasswordRules(newPassword);

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
                />
            </ChakraField.Root>

            {passwordStrength && (
                <Text
                    fontSize="sm"
                    fontWeight="bold"
                    color={
                        passwordStrength === "Weak" ? "red.500" :
                        passwordStrength === "Medium" ? "orange.400" : "green.500"
                    }
                >
                    Strength: {passwordStrength}
                </Text>
            )}

            <PasswordRulesChecklist rules={rules} fontSize="14px" />

            <ChakraField.Root required>
                <ChakraField.Label>Confirm new password</ChakraField.Label>
                <Input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm New Password"
                    size="lg"
                />
            </ChakraField.Root>

            <Button
                type="submit"
                colorPalette="brand"
                size="lg"
                w="full"
                loading={resetConfirmMutation.isPending}
                loadingText="Resetting..."
            >
                Reset Password
            </Button>

            {/* Matches every other auth form's secondary styling (see
                LoginForm.tsx for why explicit tokens, not Chakra's gray
                colorPalette defaults). */}
            <Button
                type="button"
                variant="outline"
                borderColor="fg.muted"
                color="fg.muted"
                _hover={{ bg: "bg.canvas", borderColor: "fg.muted" }}
                size="lg"
                w="full"
                onClick={handleClear}
                disabled={resetConfirmMutation.isPending}
            >
                Clear
            </Button>

            {localError && <FormAlert status="error">{localError}</FormAlert>}

            {resetConfirmMutation.isError && (
                <FormAlert status="error">{resetConfirmMutation.error.message}</FormAlert>
            )}

            {resetConfirmMutation.isSuccess && (
                <FormAlert status="success">{resetConfirmMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default PasswordResetConfirmForm;
