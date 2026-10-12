import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import FormAlert from "../ui/feedback/FormAlert";
import { useUpdateMyAccountMutation } from "./useUpdateMyAccountMutation";
import { toaster } from "../ui/toaster/toasterInstance";
import { Button } from "../ui/buttons/Button";
import { Input } from "../ui/inputs/Input";
import { Label } from "../ui/shadcn/label";

interface ProfileNameCardProps {
    name: string | null;
    /** Reports whether the name field currently differs from the saved
     * value, so AccountSettingsPage can combine it with the password
     * card's own dirty state for one page-level unsaved-changes warning. */
    onDirtyChange: (isDirty: boolean) => void;
}

/**
 * ProfileNameCard
 * ----------------------------
 * The name-change half of AccountSettingsPage: its own independent
 * mutation instance (not shared with ChangePasswordCard) so saving a name
 * change never shows a loading spinner or a stale error on the unrelated
 * password card, and vice versa.
 */
const ProfileNameCard: React.FC<ProfileNameCardProps> = ({ name, onDirtyChange }) => {
    const { t } = useTranslation("account_settings");
    const [editedName, setEditedName] = useState(name ?? "");
    const [nameError, setNameError] = useState("");

    const nameMutation = useUpdateMyAccountMutation();

    const isDirty = editedName !== (name ?? "");
    useEffect(() => {
        onDirtyChange(isDirty);
    }, [isDirty, onDirtyChange]);

    const handleNameSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        setNameError("");

        if (!editedName || editedName === name) {
            setNameError(t("profileName.noChanges"));
            return;
        }

        nameMutation.mutate(
            { name: editedName },
            {
                onSuccess: (updated) => {
                    toaster.create({ title: t("profileName.updatedToast"), type: "success" });
                    setEditedName(updated.name);
                },
            }
        );
    };

    return (
        <Card className="p-5">
            <form onSubmit={handleNameSubmit} className="flex flex-col gap-4">
                <div>
                    <SectionHeading>{t("tabs.profile")}</SectionHeading>
                    <p className="mt-1 text-sm text-fg-muted">{t("profileName.description")}</p>
                </div>
                <div className="flex flex-col gap-1.5">
                    <Label htmlFor="profile-name">{t("profileName.nameLabel")}</Label>
                    <Input
                        id="profile-name"
                        value={editedName}
                        onChange={(e) => setEditedName(e.target.value)}
                        aria-invalid={!!nameError || nameMutation.isError}
                        aria-describedby={nameError ? "name-local-error" : nameMutation.isError ? "name-mutation-error" : undefined}
                        size="lg"
                        maxLength={100}
                    />
                </div>

                {nameError && <FormAlert size="lg" status="error" id="name-local-error">{nameError}</FormAlert>}
                {nameMutation.isError && <FormAlert size="lg" status="error" id="name-mutation-error">{nameMutation.error.message}</FormAlert>}

                <Button
                    type="submit"
                    variant="brand"
                    className="self-start"
                    loading={nameMutation.isPending}
                >
                    {t("profileName.saveChanges")}
                </Button>
            </form>
        </Card>
    );
};

export default ProfileNameCard;
