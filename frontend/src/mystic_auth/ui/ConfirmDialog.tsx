import React from "react";
import { Button, Dialog, Portal, Text } from "@chakra-ui/react";

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
                <Dialog.Backdrop />
                <Dialog.Positioner>
                    <Dialog.Content>
                        <Dialog.Header>
                            <Dialog.Title>{title}</Dialog.Title>
                        </Dialog.Header>
                        <Dialog.Body>
                            <Text color="fg.muted">{description}</Text>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button variant="ghost" onClick={onCancel} disabled={isLoading}>
                                Cancel
                            </Button>
                            <Button
                                colorPalette={isDestructive ? "red" : "brand"}
                                onClick={onConfirm}
                                loading={isLoading}
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
