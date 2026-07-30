import React, { useState, useEffect } from "react";
import { Input, Button, Stack, Text } from "@chakra-ui/react";
import { Link } from "react-router";

import { useLoginMutation } from "./useLoginMutation";
import FormAlert from "../../ui/FormAlert";

interface LoginFormProps {
    onSuccess?: () => void;
    onAttempt?: () => void;
}

const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, onAttempt }) => {
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

    const handleClear = () => {
        loginMutation.reset();
        setEmail("");
        setPassword("");
    };

    return (
        <Stack
            as="form"
            onSubmit={handleSubmit}
            w="full"
            gap={4}
        >
            <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                autoComplete="email"
                required
            />

            <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                autoComplete="current-password"
                required
            />

            <Button
                type="submit"
                colorPalette="brand"
                h="10"
                px={4}
                fontSize="md"
                w="full"
                loading={loginMutation.isPending}
                loadingText="Logging in..."
            >
                Login
            </Button>

            {/* Deliberately soft/secondary so it never competes visually with
                Login. Uses this app's own border/fg tokens explicitly rather
                than Chakra's built-in gray colorPalette defaults for the
                outline variant, which in dark mode rendered a border nearly
                indistinguishable from the card background (border.default's
                dark value is a deliberately visible step up from
                bg.surface's dark value, see theme/system.ts). */}
            <Button
                type="button"
                variant="outline"
                borderColor="border.default"
                color="fg.muted"
                _hover={{ bg: "bg.canvas", borderColor: "fg.muted" }}
                h="10"
                px={4}
                fontSize="md"
                w="full"
                onClick={handleClear}
                disabled={loginMutation.isPending}
            >
                Clear
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
                    Forgot Password?
                </Link>
            </Text>

            {loginMutation.isError && (
                <FormAlert status="error">
                    {loginMutation.error.message}
                </FormAlert>
            )}

            {loginMutation.isSuccess && (
                <FormAlert status="success">
                    Login successful!
                </FormAlert>
            )}
        </Stack>
    );
};

export default LoginForm;
