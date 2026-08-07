import React, { useEffect, useState } from "react";
import { Button, Field, Input, Stack } from "@chakra-ui/react";

import Card from "../ui/Card";
import FormAlert from "../ui/FormAlert";
import { useUpdateMyAccountMutation } from "./useUpdateMyAccountMutation";
import { toaster } from "../ui/toaster/toasterInstance";
import { BRAND_SOLID_HOVER_PROPS } from "../ui/styles/buttonStyles";
import { SEARCH_INPUT_PROPS } from "../ui/styles/inputStyles";

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
    const [editedName, setEditedName] = useState(name ?? "");
    const [nameError, setNameError] = useState("");

    const nameMutation = useUpdateMyAccountMutation();

    const isDirty = editedName !== (name ?? "");
    useEffect(() => {
        onDirtyChange(isDirty);
    }, [isDirty, onDirtyChange]);

    const handleNameSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        setNameError("");

        if (!editedName || editedName === name) {
            setNameError("No changes to save");
            return;
        }

        nameMutation.mutate(
            { name: editedName },
            {
                onSuccess: (updated) => {
                    toaster.create({ title: "Profile updated", type: "success" });
                    setEditedName(updated.name);
                },
            }
        );
    };

    return (
        <Card p={5}>
            <Stack as="form" onSubmit={handleNameSubmit} gap={4}>
                <Field.Root>
                    <Field.Label>Name</Field.Label>
                    <Input
                        value={editedName}
                        onChange={(e) => setEditedName(e.target.value)}
                        aria-invalid={!!nameError || nameMutation.isError}
                        aria-describedby={nameError ? "name-local-error" : nameMutation.isError ? "name-mutation-error" : undefined}
                        {...SEARCH_INPUT_PROPS}
                    />
                </Field.Root>

                {nameError && <FormAlert status="error" id="name-local-error">{nameError}</FormAlert>}
                {nameMutation.isError && <FormAlert status="error" id="name-mutation-error">{nameMutation.error.message}</FormAlert>}

                <Button
                    type="submit"
                    colorPalette="brand"
                    alignSelf="flex-start"
                    loading={nameMutation.isPending}
                    loadingText="Saving..."
                    {...BRAND_SOLID_HOVER_PROPS}
                >
                    Save changes
                </Button>
            </Stack>
        </Card>
    );
};

export default ProfileNameCard;
