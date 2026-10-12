import React, { useEffect, useRef } from "react";
import axios from "axios";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Power, CalendarClock, Undo2, Link2Off } from "lucide-react";

import { useConfirmDeleteMyAccountMutation } from "./useConfirmDeleteMyAccountMutation";
import { Button } from "../../ui/buttons/Button";
import FormAlert from "../../ui/feedback/FormAlert";
import AuthResultPanel from "../../ui/feedback/AuthResultPanel";
import AuthInlineLink from "../../ui/links/AuthInlineLink";

interface ConfirmDeleteAccountButtonProps {
    token: string;
    onSuccess?: () => void;
}

// D1: the only code the backend can return for a dead/reused/tampered token
// (account_deletion_confirm_handler.py returns the same code whether the
// token never existed, already expired, or was already redeemed), so unlike
// password-reset-confirm there's only one code to check for.
function isDeadDeleteLinkError(error: Error): boolean {
    const cause = error.cause;
    if (!axios.isAxiosError(cause)) return false;
    return cause.response?.data?.code === "INVALID_OR_EXPIRED_DELETE_TOKEN";
}

// Mirrors VerifyAccountButton.tsx: a deliberate click (not auto-fired on page
// load) redeems the token, since a link prefetched or scanned by an email
// client or link-preview bot must not silently consume a single-use token.
const ConfirmDeleteAccountButton: React.FC<ConfirmDeleteAccountButtonProps> = ({ token, onSuccess }) => {
    const { t } = useTranslation("account_settings");
    const confirmMutation = useConfirmDeleteMyAccountMutation();

    // Same "fire onSuccess exactly once, via a ref" reasoning as
    // VerifyAccountButton.tsx.
    const onSuccessRef = useRef(onSuccess);
    const firedRef = useRef(false);

    useEffect(() => {
        onSuccessRef.current = onSuccess;
    });

    useEffect(() => {
        if (confirmMutation.isSuccess && !firedRef.current) {
            firedRef.current = true;
            onSuccessRef.current?.();
        }
    }, [confirmMutation.isSuccess]);

    const handleConfirm = () => {
        confirmMutation.mutate({ token });
    };

    // D3/R3: a dead token can only fail the same way again, so a failed
    // confirm against it swaps straight to "here's what to do next" instead
    // of leaving the same doomed button up for another click.
    if (confirmMutation.isError && isDeadDeleteLinkError(confirmMutation.error)) {
        return (
            <AuthResultPanel
                icon={<Link2Off size={26} />}
                variant="error"
                title={t("confirmDeletePage.linkExpiredTitle")}
                description={t("confirmDeletePage.linkExpiredDescription")}
            >
                <Button asChild variant="outline" size="lg" className="w-full">
                    <Link to="/login">{t("confirmDeletePage.backToLogin")}</Link>
                </Button>
            </AuthResultPanel>
        );
    }

    return (
        <div className="flex flex-col items-center w-full gap-3">
            {/* D2/D4: what happens, in a red-tinted block instead of red heading
                text (design.md's destructive-actions rules keep the solid red
                button and red icon, but reserve the alarming red text for the
                confirmation itself). */}
            <div className="grid w-full gap-3 rounded-xl border border-red-200 bg-red-50/65 p-3 dark:border-red-900/70 dark:bg-red-950/25 sm:grid-cols-3 sm:gap-2 sm:p-4">
                {[
                    { icon: <Power size={17} />, title: t("confirmDeletePage.warnDeactivatedTitle"), sub: t("confirmDeletePage.warnDeactivatedSub") },
                    { icon: <CalendarClock size={17} />, title: t("confirmDeletePage.warnDeletedTitle"), sub: t("confirmDeletePage.warnDeletedSub") },
                    { icon: <Undo2 size={17} />, title: t("confirmDeletePage.warnChangedMindTitle"), sub: t("confirmDeletePage.warnChangedMindSub") },
                ].map((item, idx) => (
                    <div key={idx} className="flex flex-row items-start gap-3 rounded-lg p-2 sm:flex-col sm:items-center sm:p-3 sm:text-center">
                        <div className="flex size-9 shrink-0 items-center justify-center text-fg-error">
                            {item.icon}
                        </div>
                        <div className="flex flex-col gap-1">
                            <p className="text-sm font-semibold leading-5 text-fg-default">
                                {item.title}
                            </p>
                            <p className="text-xs leading-5 text-fg-muted">
                                {item.sub}
                            </p>
                        </div>
                    </div>
                ))}
            </div>

            <Button
                onClick={handleConfirm}
                variant="destructive"
                size="lg"
                className="w-full shadow-[0_8px_18px_-12px_var(--fg-error)]"
                loading={confirmMutation.isPending}
                disabled={!token}
            >
                {t("confirmDeleteButton.submitButton")}
            </Button>

            {/* D3: "Cancel, keep my account" to "/", not "Back to Account
                Settings" - a signed-out visitor opening this link on another
                device would just bounce off account settings to /login. */}
            <Button asChild variant="outline" size="lg" className="w-full">
                <Link to="/">{t("confirmDeletePage.cancelKeepAccount")}</Link>
            </Button>

            {!token && (
                <p className="text-sm text-fg-muted text-center">
                    {t("confirmDeletePage.noTokenHint")}
                </p>
            )}

            {confirmMutation.isError && (
                <FormAlert status="error">{confirmMutation.error.message}</FormAlert>
            )}

            <p className="mt-1 text-xs leading-5 text-fg-muted text-center">
                {t("confirmDeletePage.agreeToTermsPrefix")}{" "}
                <AuthInlineLink to="/terms">{t("confirmDeletePage.termsOfService")}</AuthInlineLink>{" "}
                {t("confirmDeletePage.and")}{" "}
                <AuthInlineLink to="/privacy">{t("confirmDeletePage.privacyPolicy")}</AuthInlineLink>
            </p>
        </div>
    );
};

export default ConfirmDeleteAccountButton;
