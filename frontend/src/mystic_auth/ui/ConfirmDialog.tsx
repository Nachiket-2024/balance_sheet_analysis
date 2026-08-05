import React from "react";
import { Button, Dialog, Portal } from "@chakra-ui/react";
import { DIALOG_BACKDROP_PROPS, DIALOG_CONTENT_PROPS } from "./styles/dialogStyles";
import { BRAND_SOLID_HOVER_PROPS, DESTRUCTIVE_SOLID_HOVER_PROPS, SECONDARY_BUTTON_PROPS } from "./styles/buttonStyles";

interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel?: string;
    isDestructive?: boolean;
    isLoading?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

/**
 * Shared confirmation modal for destructive/irreversible admin actions
 * (delete policy, delete user, revoke a policy assignment) so none of those
 * flows fire on a single accidental click. Controlled entirely by the
 * caller (isOpen/onConfirm/onCancel) rather than owning its own open state,
 * so the caller can tie it to whichever row/action triggered it.
 */
const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
    isOpen,
    title,
    description,
    confirmLabel = "Confirm",
    isDestructive = true,
    isLoading = false,
    onConfirm,
    onCancel,
}) => {
    return (
        <Dialog.Root open={isOpen} onOpenChange={(details) => !details.open && onCancel()} role="alertdialog">
            <Portal>
                <Dialog.Backdrop {...DIALOG_BACKDROP_PROPS} />
                <Dialog.Positioner>
                    <Dialog.Content {...DIALOG_CONTENT_PROPS}>
                        <Dialog.Header>
                            <Dialog.Title>{title}</Dialog.Title>
                        </Dialog.Header>
                        <Dialog.Body>
                            {/* Dialog.Description (not a plain Text) so Ark UI wires
                                aria-describedby on the dialog itself : a screen reader
                                announcing this alertdialog reads the warning text, not
                                just the title, without a caller having to do it by hand. */}
                            <Dialog.Description color="fg.muted">{description}</Dialog.Description>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button onClick={onCancel} disabled={isLoading} {...SECONDARY_BUTTON_PROPS}>
                                Cancel
                            </Button>
                            <Button
                                colorPalette={isDestructive ? "red" : "brand"}
                                onClick={onConfirm}
                                loading={isLoading}
                                {...(isDestructive ? DESTRUCTIVE_SOLID_HOVER_PROPS : BRAND_SOLID_HOVER_PROPS)}
                            >
                                {confirmLabel}
                            </Button>
                        </Dialog.Footer>
                        <Dialog.CloseTrigger />
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>
        </Dialog.Root>
    );
};

export default ConfirmDialog;
