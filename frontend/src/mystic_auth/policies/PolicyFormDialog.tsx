import React, { useState } from "react";
import { Button, Dialog, Field, Input, Portal, Stack, Textarea } from "@chakra-ui/react";

import type { PolicyRead } from "../api/policies_api";
import FormAlert from "../ui/FormAlert";
import ConfirmDialog from "../ui/ConfirmDialog";
import { DIALOG_BACKDROP_PROPS, DIALOG_CONTENT_PROPS } from "../ui/styles/dialogStyles";
import { BRAND_SOLID_HOVER_PROPS, SECONDARY_BUTTON_PROPS } from "../ui/styles/buttonStyles";

export interface PolicyFormValues {
    name: string;
    description: string;
    actions: string[];
    resource_type: string;
    conditions?: Record<string, unknown>;
}

interface PolicyFormDialogProps {
    isOpen: boolean;
    /** Present when editing an existing policy; absent when creating. */
    policy?: PolicyRead;
    isSaving: boolean;
    errorMessage: string | null;
    onSubmit: (values: PolicyFormValues) => void;
    onClose: () => void;
}

function actionsToText(actions: string[]): string {
    return actions.join(", ");
}

function textToActions(text: string): string[] {
    return text
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);
}

/**
 * PolicyFormDialog
 * ----------------------------
 * Shared create/edit form for a Policy: one component instead of separate
 * "create" and "edit" modals, since the fields and validation are identical
 * (see PolicyBase on the backend). `policy` presence alone distinguishes
 * the two modes.
 */
const PolicyFormDialog: React.FC<PolicyFormDialogProps> = ({
    isOpen,
    policy,
    isSaving,
    errorMessage,
    onSubmit,
    onClose,
}) => {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [actionsText, setActionsText] = useState("");
    const [resourceType, setResourceType] = useState("");
    const [conditionsText, setConditionsText] = useState("");
    const [conditionsError, setConditionsError] = useState<string | null>(null);

    // Snapshot of every field's value right after the form was last reset
    // (dialog opened), compared against current values to detect unsaved
    // edits before a close attempt discards them.
    const [initialSnapshot, setInitialSnapshot] = useState("");

    // Reset the form to the policy being edited (or blank, for create)
    // every time the dialog opens. Adjusted during render (React's
    // documented pattern for state derived from props) rather than in an
    // effect, since setState-in-effect causes an extra, avoidable render.
    const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
    if (isOpen && !prevIsOpen) {
        setPrevIsOpen(isOpen);
        const initialName = policy?.name ?? "";
        const initialDescription = policy?.description ?? "";
        const initialActionsText = policy ? actionsToText(policy.actions) : "";
        const initialResourceType = policy?.resource_type ?? "";
        const initialConditionsText = policy?.conditions ? JSON.stringify(policy.conditions, null, 2) : "";

        setName(initialName);
        setDescription(initialDescription);
        setActionsText(initialActionsText);
        setResourceType(initialResourceType);
        setConditionsText(initialConditionsText);
        setConditionsError(null);
        setInitialSnapshot(
            JSON.stringify([initialName, initialDescription, initialActionsText, initialResourceType, initialConditionsText])
        );
    } else if (isOpen !== prevIsOpen) {
        setPrevIsOpen(isOpen);
    }

    const isDirty =
        JSON.stringify([name, description, actionsText, resourceType, conditionsText]) !== initialSnapshot;

    // A themed ConfirmDialog, not window.confirm: the latter is an
    // unstyled native browser dialog, the only one in an otherwise fully
    // themed app.
    const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);

    const requestClose = () => {
        if (isDirty) {
            setShowDiscardConfirm(true);
            return;
        }
        onClose();
    };

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        let conditions: Record<string, unknown> | undefined;
        if (conditionsText.trim()) {
            try {
                conditions = JSON.parse(conditionsText);
            } catch {
                setConditionsError("Conditions must be valid JSON");
                return;
            }
        }
        setConditionsError(null);

        onSubmit({
            name,
            description,
            actions: textToActions(actionsText),
            resource_type: resourceType,
            conditions,
        });
    };

    return (
        <>
            <Dialog.Root open={isOpen} onOpenChange={(details) => !details.open && requestClose()}>
                <Portal>
                    <Dialog.Backdrop {...DIALOG_BACKDROP_PROPS} />
                    <Dialog.Positioner>
                        <Dialog.Content {...DIALOG_CONTENT_PROPS}>
                            <Dialog.Header>
                                <Dialog.Title>{policy ? "Edit Policy" : "Create Policy"}</Dialog.Title>
                            </Dialog.Header>
                            <Dialog.Body>
                                <Stack as="form" id="policy-form" onSubmit={handleSubmit} gap={4}>
                                    <Field.Root required>
                                        <Field.Label>Name</Field.Label>
                                        <Input
                                            value={name}
                                            onChange={(e) => setName(e.target.value)}
                                            placeholder="e.g. document_reviewer"
                                        />
                                    </Field.Root>

                                    <Field.Root>
                                        <Field.Label>Description</Field.Label>
                                        <Input
                                            value={description}
                                            onChange={(e) => setDescription(e.target.value)}
                                            placeholder="What this policy grants and why"
                                        />
                                    </Field.Root>

                                    <Field.Root required>
                                        <Field.Label>Actions</Field.Label>
                                        <Input
                                            value={actionsText}
                                            onChange={(e) => setActionsText(e.target.value)}
                                            placeholder="e.g. documents:view, documents:edit"
                                        />
                                        <Field.HelperText>Comma-separated action identifiers</Field.HelperText>
                                    </Field.Root>

                                    <Field.Root required>
                                        <Field.Label>Resource type</Field.Label>
                                        <Input
                                            value={resourceType}
                                            onChange={(e) => setResourceType(e.target.value)}
                                            placeholder='e.g. "documents" or "*" for any'
                                        />
                                    </Field.Root>

                                    <Field.Root invalid={!!conditionsError}>
                                        <Field.Label>Conditions (JSON, optional)</Field.Label>
                                        <Textarea
                                            value={conditionsText}
                                            onChange={(e) => setConditionsText(e.target.value)}
                                            placeholder='e.g. { "self_only": true }'
                                            rows={4}
                                            fontFamily="mono"
                                        />
                                        {conditionsError && <Field.ErrorText>{conditionsError}</Field.ErrorText>}
                                    </Field.Root>

                                    {errorMessage && <FormAlert status="error">{errorMessage}</FormAlert>}
                                </Stack>
                            </Dialog.Body>
                            <Dialog.Footer>
                                <Button onClick={requestClose} disabled={isSaving} {...SECONDARY_BUTTON_PROPS}>
                                    Cancel
                                </Button>
                                <Button
                                    type="submit"
                                    form="policy-form"
                                    colorPalette="brand"
                                    loading={isSaving}
                                    loadingText="Saving..."
                                    {...BRAND_SOLID_HOVER_PROPS}
                                >
                                    {policy ? "Save changes" : "Create policy"}
                                </Button>
                            </Dialog.Footer>
                            <Dialog.CloseTrigger />
                        </Dialog.Content>
                    </Dialog.Positioner>
                </Portal>
            </Dialog.Root>

            <ConfirmDialog
                isOpen={showDiscardConfirm}
                title="Discard unsaved changes?"
                description="Your edits to this policy haven't been saved. Closing now will discard them."
                confirmLabel="Discard"
                onConfirm={() => {
                    setShowDiscardConfirm(false);
                    onClose();
                }}
                onCancel={() => setShowDiscardConfirm(false)}
            />
        </>
    );
};

export default PolicyFormDialog;
