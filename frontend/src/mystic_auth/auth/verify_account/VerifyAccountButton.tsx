import React, { useEffect, useRef } from "react";
import { Stack, Button, Spinner } from "@chakra-ui/react";

import { useVerifyAccountMutation } from "./useVerifyAccountMutation";
import { BRAND_SOLID_HOVER_PROPS } from "../../ui/styles/buttonStyles";
import FormAlert from "../../ui/FormAlert";

interface VerifyAccountButtonProps {
    token: string;
    email: string;
    onSuccess?: () => void;
}

const VerifyAccountButton: React.FC<VerifyAccountButtonProps> = ({ token, email, onSuccess }) => {
    const verifyMutation = useVerifyAccountMutation();

    // Fires onSuccess exactly once per successful verification, not once
    // per render where onSuccess's identity happens to change: `onSuccess`
    // is deliberately left out of the dependency array (most callers pass
    // an inline arrow function, a fresh identity every render) and read via
    // a ref instead, so a later, unrelated re-render of the page while
    // isSuccess is still true can't re-fire this (e.g. re-navigating away
    // a second time).
    const onSuccessRef = useRef(onSuccess);
    const firedRef = useRef(false);

    useEffect(() => {
        onSuccessRef.current = onSuccess;
    });

    useEffect(() => {
        if (verifyMutation.isSuccess && !firedRef.current) {
            firedRef.current = true;
            onSuccessRef.current?.();
        }
    }, [verifyMutation.isSuccess]);

    const handleVerify = () => {
        verifyMutation.mutate({ token, email });
    };

    return (
        <Stack align="center" w="full">
            <Button
                onClick={handleVerify}
                colorPalette="brand"
                size="lg"
                w="full"
                {...BRAND_SOLID_HOVER_PROPS}
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
                <FormAlert status="error">{verifyMutation.error.message}</FormAlert>
            )}

            {verifyMutation.isSuccess && (
                <FormAlert status="success">{verifyMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default VerifyAccountButton;
