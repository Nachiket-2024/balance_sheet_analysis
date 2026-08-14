import React, { useState, useEffect } from "react";
import { Input, Button, Stack, Text } from "@chakra-ui/react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";

import { useLoginMutation } from "./useLoginMutation";
import FormAlert from "../../ui/FormAlert";
import { FAST_HOVER_TRANSITION } from "../../ui/styles/buttonStyles";

interface LoginFormProps {
    onSuccess?: () => void;
    onAttempt?: () => void;
}

const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, onAttempt }) => {
    const { t } = useTranslation("auth");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    const loginMutation = useLoginMutation();

    useEffect(() => {
        if (loginMutation.isSuccess && onSuccess) {
            onSuccess();
        }
    }, [loginMutation.isSuccess, onSuccess]);

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        onAttempt?.();
        loginMutation.mutate({ email, password });
    };

    return (
        <Stack
            as="form"
            onSubmit={handleSubmit}
            w="full"
            gap={4}
        >
            {/* bg.canvas (not bg.surface, which matches this form's own Card
                background) so fields read as recessed into the card instead
                of just a thin outline floating on an identical fill;
                colorPalette="brand" gives the focus ring the app's teal
                instead of Chakra's default gray one. */}
            <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("login.emailPlaceholder")}
                autoComplete="email"
                bg="bg.canvas"
                colorPalette="brand"
                required
                aria-invalid={loginMutation.isError}
                aria-describedby={loginMutation.isError ? "login-error" : undefined}
            />

            <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("login.passwordPlaceholder")}
                autoComplete="current-password"
                bg="bg.canvas"
                colorPalette="brand"
                required
                aria-invalid={loginMutation.isError}
                aria-describedby={loginMutation.isError ? "login-error" : undefined}
            />

            {/* Solid variant's default hover is only colorPalette.solid at 90%
                opacity - too subtle a shift to read as a hover state.
                brand.700 (one step past brand.600's solid) gives a real,
                visible contrast bump instead. */}
            <Button
                type="submit"
                colorPalette="brand"
                h="10"
                px={4}
                fontSize="md"
                w="full"
                loading={loginMutation.isPending}
                loadingText={t("login.loggingIn")}
                _hover={{ bg: "brand.700" }}
                transition={FAST_HOVER_TRANSITION}
            >
                {t("login.submitButton")}
            </Button>

            <Text
                fontSize="md"
                textAlign="right"
                width="100%"
            >
                <Link
                    to="/password-reset-request"
                    style={{
                        color: "var(--chakra-colors-brand-fg)",
                        fontWeight: 600,
                    }}
                >
                    {t("login.forgotPassword")}
                </Link>
            </Text>

            {loginMutation.isError && (
                <FormAlert status="error" id="login-error">
                    {loginMutation.error.message}
                </FormAlert>
            )}

            {loginMutation.isSuccess && (
                <FormAlert status="success">
                    {t("login.loginSuccess")}
                </FormAlert>
            )}
        </Stack>
    );
};

export default LoginForm;
