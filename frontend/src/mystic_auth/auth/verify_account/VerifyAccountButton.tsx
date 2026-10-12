import React, { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { useVerifyAccountMutation } from "./useVerifyAccountMutation";
import { Button } from "../../ui/buttons/Button";
import FormAlert from "../../ui/feedback/FormAlert";

interface VerifyAccountButtonProps {
    token: string;
    email: string;
    onSuccess?: () => void;
    /** V2: lets the page move focus to the resend form once a verify
     * attempt fails, since retrying the same link can only fail again. */
    onError?: () => void;
}

const VerifyAccountButton: React.FC<VerifyAccountButtonProps> = ({ token, email, onSuccess, onError }) => {
    const { t } = useTranslation("auth");
    const verifyMutation = useVerifyAccountMutation();

    // Fires onSuccess/onError exactly once per settled mutation, not once per
    // render where the callback's identity happens to change (most callers
    // pass an inline arrow function). Read via a ref instead of the
    // dependency array, so an unrelated re-render while isSuccess/isError is
    // still true can't re-fire it.
    const onSuccessRef = useRef(onSuccess);
    const onErrorRef = useRef(onError);
    const firedRef = useRef(false);

    useEffect(() => {
        onSuccessRef.current = onSuccess;
        onErrorRef.current = onError;
    });

    useEffect(() => {
        if (firedRef.current) return;
        if (verifyMutation.isSuccess) {
            firedRef.current = true;
            onSuccessRef.current?.();
        } else if (verifyMutation.isError) {
            firedRef.current = true;
            onErrorRef.current?.();
        }
    }, [verifyMutation.isSuccess, verifyMutation.isError]);

    const handleVerify = () => {
        verifyMutation.mutate({ token, email });
    };

    return (
        <div className="flex flex-col items-center w-full gap-3">
            {verifyMutation.isError && (
                <FormAlert status="error">{verifyMutation.error.message}</FormAlert>
            )}

            <Button
                onClick={handleVerify}
                variant="brand"
                size="lg"
                className="w-full"
                loading={verifyMutation.isPending}
                // Mirrors ConfirmDeleteAccountButton.tsx: no token means there's
                // nothing to submit, and a failed attempt can only fail the
                // same way again, so disable rather than leave it clickable.
                disabled={!token || verifyMutation.isSuccess || verifyMutation.isError}
            >
                {verifyMutation.isPending ? t("verifyAccountButton.verifying") : t("verifyAccountButton.submitButton")}
            </Button>

            {verifyMutation.isSuccess && (
                <FormAlert status="success">{verifyMutation.data.message}</FormAlert>
            )}
        </div>
    );
};

export default VerifyAccountButton;
