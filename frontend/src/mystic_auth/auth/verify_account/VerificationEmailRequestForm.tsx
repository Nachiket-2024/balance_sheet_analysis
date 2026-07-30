import React, { useState } from "react";
import { Button, Input, Stack } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";

import { useVerificationEmailRequestMutation } from "./useVerificationEmailRequestMutation";
import FormAlert from "../../ui/FormAlert";

interface VerificationEmailRequestFormProps {
    initialEmail?: string;
}

const VerificationEmailRequestForm: React.FC<VerificationEmailRequestFormProps> = ({ initialEmail = "" }) => {
    const [email, setEmail] = useState(initialEmail);
    const [cooldown, setCooldown] = useState(0);
    const requestMutation = useVerificationEmailRequestMutation();

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

        requestMutation.mutate({ email });
        startCooldown();
    };

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full" gap={3}>
            <ChakraField.Root required>
                <ChakraField.Label>Email</ChakraField.Label>
                <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    size="lg"
                    disabled={requestMutation.isPending}
                />
            </ChakraField.Root>

            <Button
                type="submit"
                variant="outline"
                borderColor="brand.500"
                color="brand.500"
                _hover={{ bg: "bg.canvas", borderColor: "brand.500" }}
                size="lg"
                w="full"
                loading={requestMutation.isPending}
                disabled={cooldown > 0 || requestMutation.isPending}
                loadingText="Sending..."
            >
                {cooldown > 0 ? `Try again in ${cooldown}s` : "Send New Verification Link"}
            </Button>

            {requestMutation.isError && (
                <FormAlert status="error">{requestMutation.error.message}</FormAlert>
            )}

            {requestMutation.isSuccess && (
                <FormAlert status="success">{requestMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default VerificationEmailRequestForm;
