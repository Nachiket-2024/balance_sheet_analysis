import React, { useState } from "react";
import { Stack, Input, Button, Text, Box } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { useSignupMutation } from "./useSignupMutation";
import FormAlert from "../../ui/FormAlert";

// Shared password policy logic and checklist UI, kept identical to
// PasswordResetConfirmForm so the two flows can't drift apart again.
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../password_rules/passwordRules";
import PasswordRulesChecklist from "../password_rules/PasswordRulesChecklist";

const SignupForm: React.FC = () => {
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

        const passwordError = validatePassword(password);
        if (passwordError) {
            setLocalError(passwordError);
            return;
        }

        if (password !== confirmPassword) {
            setLocalError("Passwords do not match");
            return;
        }

        setLocalError("");
        signupMutation.mutate({ name, email, password });
    };

    const handleClear = () => {
        setName(""); setEmail(""); setPassword(""); setConfirmPassword("");
        setLocalError(""); setPasswordStrength("");
        signupMutation.reset();
    };

    const rules = checkPasswordRules(password);

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full">
            <Stack direction="row">
                <ChakraField.Root required flex={1}>
                    <ChakraField.Label>Name</ChakraField.Label>
                    <Input
                        type="text"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        placeholder="Enter your name"
                    />
                </ChakraField.Root>

                <ChakraField.Root required flex={1}>
                    <ChakraField.Label>Email</ChakraField.Label>
                    <Input
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder="Enter your email"
                    />
                </ChakraField.Root>
            </Stack>

            <ChakraField.Root required>
                <ChakraField.Label>Password</ChakraField.Label>
                <Input
                    type="password"
                    value={password}
                    onChange={e => handlePasswordChange(e.target.value)}
                    placeholder="Enter password"
                />
                {passwordStrength && (
                    <Text
                        mt={1}
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
            </ChakraField.Root>

            <PasswordRulesChecklist rules={rules} fontSize="15px" />

            <ChakraField.Root required>
                <ChakraField.Label>Confirm Password</ChakraField.Label>
                <Input
                    type="password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="Confirm password"
                />
            </ChakraField.Root>

            {localError && <FormAlert status="error">{localError}</FormAlert>}
            {signupMutation.isError && (
                <FormAlert status="error">{signupMutation.error.message}</FormAlert>
            )}
            {signupMutation.isSuccess && (
                <FormAlert status="success">{signupMutation.data.message}</FormAlert>
            )}

            <Box display="flex" alignItems="center">
                {/* Signup shows a spinner and disables itself while the request
                    is in flight, preventing double-submit. */}
                <Stack direction="row">
                    <Button
                        type="submit"
                        colorPalette="brand"
                        loading={signupMutation.isPending}
                        loadingText="Signing up..."
                    >
                        Signup
                    </Button>

                    {/* Secondary/soft styling to match every other auth form's
                        Clear button: explicit tokens rather than Chakra's gray
                        colorPalette defaults, which read as an almost-invisible
                        border in dark mode. */}
                    <Button
                        type="button"
                        onClick={handleClear}
                        variant="outline"
                        borderColor="fg.muted"
                        color="fg.muted"
                        _hover={{ bg: "bg.canvas", borderColor: "fg.muted" }}
                        disabled={signupMutation.isPending}
                    >
                        Clear
                    </Button>
                </Stack>

                <Box display="flex" alignItems="center" ml="auto">
                    <Text mr={2} color="fg.muted" fontSize="16px">
                        Already have an account?
                    </Text>
                    <Button
                        type="button"
                        colorPalette="brand"
                        variant="outline"
                        size="sm"
                        borderColor="brand.500"
                        onClick={() => (window.location.href = "/login")}
                    >
                        Login
                    </Button>
                </Box>
            </Box>
        </Stack>
    );
};

export default SignupForm;
