import React, { useState } from "react";
import { Stack, Input, Button } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { usePasswordResetRequestMutation } from "./usePasswordResetRequestMutation";
import { useCooldown } from "../useCooldown";
import FormAlert from "../../ui/FormAlert";

const PasswordResetRequestForm: React.FC = () => {
    const [email, setEmail] = useState("");
    const { cooldown, startCooldown } = useCooldown();

    const resetRequestMutation = usePasswordResetRequestMutation();

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        if (cooldown > 0) {
            return;
        }

        resetRequestMutation.mutate({ email });
        startCooldown();
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

            {/* Solid variant's default hover is only colorPalette.solid at 90%
                opacity - too subtle a shift to read as a hover state (see
                LoginForm.tsx's Login button for the same fix). */}
            <Button
                type="submit"
                colorPalette="brand"
                size="lg"
                w="full"
                loading={resetRequestMutation.isPending}
                disabled={cooldown > 0 || resetRequestMutation.isPending}
                loadingText="Sending..."
                _hover={{ bg: "brand.700" }}
            >
                {cooldown > 0 ? `Try again in ${cooldown}s` : "Request Password Reset"}
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
