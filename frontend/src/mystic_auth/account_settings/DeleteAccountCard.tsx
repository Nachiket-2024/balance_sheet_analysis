import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import FormAlert from "../ui/feedback/FormAlert";
import PasswordInput from "../ui/inputs/PasswordInput";
import ConfirmDialog from "../ui/feedback/ConfirmDialog";
import { toaster } from "../ui/toaster/toasterInstance";
import { Button } from "../ui/buttons/Button";
import { Label } from "../ui/shadcn/label";
import { useDeleteMyAccountMutation } from "./useDeleteMyAccountMutation";

interface DeleteAccountCardProps {
    hasPassword: boolean;
}

/**
 * DeleteAccountCard
 * ----------------------------
 * Self-service counterpart to the permission-protected "Delete user" action on UsersPage: a
 * ConfirmDialog step since this is destructive, gated by the same
 * current-password re-confirmation ChangePasswordCard uses when the account
 * has a password. Deliberately soft-delete only, never immediate: the copy
 * below matches the recoverable-for-a-grace-period behavior DELETE /users/me
 * actually implements server-side (see docs/mystic_auth/security/decisions.md).
 *
 * An OAuth-only account (hasPassword=false) has no password to re-confirm
 * with, so it isn't deleted synchronously from this dialog. DELETE /users/me
 * instead sends a confirmation email (confirmation_required=true in the
 * response, see useDeleteMyAccountMutation.ts), and this card shows "check
 * your email" messaging instead of the deleted-and-signed-out toast/redirect.
 */
const DeleteAccountCard: React.FC<DeleteAccountCardProps> = ({ hasPassword }) => {
    const { t } = useTranslation("account_settings");
    const navigate = useNavigate();
    const [currentPassword, setCurrentPassword] = useState("");
    const [formError, setFormError] = useState("");
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [confirmationSent, setConfirmationSent] = useState(false);

    const deleteMutation = useDeleteMyAccountMutation();

    const handleRequestDelete = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        setFormError("");

        if (hasPassword && !currentPassword) {
            setFormError(t("deleteAccount.currentPasswordRequired"));
            return;
        }

        setConfirmOpen(true);
    };

    const handleConfirmDelete = () => {
        deleteMutation.mutate(
            { current_password: hasPassword ? currentPassword : undefined },
            {
                onSuccess: (data) => {
                    setConfirmOpen(false);

                    if (data.confirmation_required) {
                        setConfirmationSent(true);
                        return;
                    }

                    toaster.create({ title: t("deleteAccount.deletedToast"), type: "success" });
                    navigate("/login");
                },
                onError: () => setConfirmOpen(false),
            }
        );
    };

    return (
        // Softer red tint than a solid bg-red-50/dark:bg-red-950 - enough to
        // mark this card as destructive at a glance, but not so saturated
        // that the password field sitting inside it reads as an error state
        // just from the surrounding color (see git history/review for why).
        <Card className="max-w-2xl flex-1 basis-80 border-red-200 border-s-4 border-s-red-500 bg-red-50/60 p-5 shadow-none dark:border-red-800/60 dark:border-s-red-400 dark:bg-red-950/40">
            <SectionHeading className="mb-2 text-fg-error">
                {t("deleteAccount.title")}
            </SectionHeading>
            <p className="text-fg-muted text-sm mb-4">
                {hasPassword ? t("deleteAccount.description") : t("deleteAccount.oauthOnlyDescription")}
            </p>

            {confirmationSent ? (
                <FormAlert size="lg" status="success">{t("deleteAccount.confirmationEmailSent")}</FormAlert>
            ) : (
                <form onSubmit={handleRequestDelete} className="flex flex-col gap-4">
                    {hasPassword && (
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="delete-account-current-password">{t("deleteAccount.currentPasswordLabel")}</Label>
                            <PasswordInput
                                id="delete-account-current-password"
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                placeholder={t("deleteAccount.currentPasswordPlaceholder")}
                                aria-invalid={!!formError || deleteMutation.isError}
                                aria-describedby={
                                    formError ? "delete-account-local-error" : deleteMutation.isError ? "delete-account-mutation-error" : undefined
                                }
                                size="lg"
                            />
                        </div>
                    )}

                    {formError && <FormAlert size="lg" status="error" id="delete-account-local-error">{formError}</FormAlert>}
                    {deleteMutation.isError && (
                        <FormAlert size="lg" status="error" id="delete-account-mutation-error">{deleteMutation.error.message}</FormAlert>
                    )}

                    <Button
                        type="submit"
                        variant="destructive"
                        className="self-start"
                    >
                        {t("deleteAccount.deleteButton")}
                    </Button>
                </form>
            )}

            <ConfirmDialog
                isOpen={confirmOpen}
                title={t("deleteAccount.confirmTitle")}
                description={hasPassword ? t("deleteAccount.confirmDescription") : t("deleteAccount.oauthOnlyConfirmDescription")}
                confirmLabel={hasPassword ? t("deleteAccount.confirmButton") : t("deleteAccount.oauthOnlyConfirmButton")}
                isLoading={deleteMutation.isPending}
                onConfirm={handleConfirmDelete}
                onCancel={() => setConfirmOpen(false)}
            />
        </Card>
    );
};

export default DeleteAccountCard;
