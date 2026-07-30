import React, { useState } from "react";
import { Stack, Input, Button } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { usePasswordResetRequestMutation } from "./usePasswordResetRequestMutation";
import FormAlert from "../../ui/FormAlert";

const PasswordResetRequestForm: React.FC = () => {
    const [email, setEmail] = useState("");
    const [cooldown, setCooldown] = useState(0);

    const resetRequestMutation = usePasswordResetRequestMutation();

    const startCooldown = () => {
        setCooldown(60);

        const interval = setInterval(() => {
            setCooldown((prev) => {
                if (prev <= 1) {
                    clearInterval(interval);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        if (cooldown > 0) {
            return;
        }

        resetRequestMutation.mutate({ email });
        startCooldown();
    };

    const handleClear = () => {
        resetRequestMutation.reset();
        setEmail("");
        setCooldown(0);
    };

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full">
            <ChakraField.Root required>
                <ChakraField.Label>Email</ChakraField.Label>
                <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    size="lg"
                    autoFocus
                    disabled={resetRequestMutation.isPending}
                />
            </ChakraField.Root>

            <Button
                type="submit"
                colorPalette="brand"
                size="lg"
                w="full"
                loading={resetRequestMutation.isPending}
                disabled={cooldown > 0 || resetRequestMutation.isPending}
                loadingText="Sending..."
            >
                {cooldown > 0 ? `Try again in ${cooldown}s` : "Request Password Reset"}
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
                disabled={resetRequestMutation.isPending}
            >
                Clear
            </Button>

            {resetRequestMutation.isError && (
                <FormAlert status="error">{resetRequestMutation.error.message}</FormAlert>
            )}

            {resetRequestMutation.isSuccess && (
                <FormAlert status="success">{resetRequestMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default PasswordResetRequestForm;
