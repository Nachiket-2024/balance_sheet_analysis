import React, { useEffect } from "react";
import { Stack, Button, Text, Spinner } from "@chakra-ui/react";

import { useVerifyAccountMutation } from "./useVerifyAccountMutation";

interface VerifyAccountButtonProps {
    token: string;
    email: string;
    onSuccess?: () => void;
}

const VerifyAccountButton: React.FC<VerifyAccountButtonProps> = ({ token, email, onSuccess }) => {
    const verifyMutation = useVerifyAccountMutation();

    useEffect(() => {
        if (verifyMutation.isSuccess && onSuccess) onSuccess();
    }, [verifyMutation.isSuccess, onSuccess]);

    const handleVerify = () => {
        verifyMutation.mutate({ token, email });
    };

    return (
        <Stack align="center" w="full">
            <Button
                onClick={handleVerify}
                colorPalette="brand"
                w="60%"
            >
                {verifyMutation.isPending ? (
                    <>
                        <Spinner size="sm" mr={2} /> Verifying...
                    </>
                ) : (
                    "Verify Account"
                )}
            </Button>

            {verifyMutation.isError && (
                <Text fontSize="sm" color="red.500">
                    {verifyMutation.error.message}
                </Text>
            )}

            {verifyMutation.isSuccess && (
                <Text fontSize="sm" color="green.500" fontWeight="medium">
                    {verifyMutation.data.message}
                </Text>
            )}
        </Stack>
    );
};

export default VerifyAccountButton;
