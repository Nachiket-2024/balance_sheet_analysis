import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
    Dialog,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "../shadcn/dialog";
import { Button } from "../buttons/Button";
import { DIALOG_FOOTER_CLASSNAME, DIALOG_HEADER_CLASSNAME, DIALOG_PANEL_CLASSNAME } from "../styles/dialogStyles";

interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel?: string;
    isDestructive?: boolean;
    isLoading?: boolean;
    confirmDisabled?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    onRetry?: () => void;
    retryLabel?: string;
    returnFocusElement?: HTMLElement | null;
}

/**
 * Shared confirmation modal for destructive/irreversible management actions
 * (delete policy, delete user, revoke a policy assignment) so none of those
 * flows fire on a single accidental click. Controlled entirely by the
 * caller (isOpen/onConfirm/onCancel) rather than owning its own open state,
 * so the caller can tie it to whichever row/action triggered it.
 */
const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
    isOpen,
    title,
    description,
    confirmLabel,
    isDestructive = true,
    isLoading = false,
    confirmDisabled = false,
    onConfirm,
    onCancel,
    onRetry,
    retryLabel,
    returnFocusElement,
}) => {
    const { t } = useTranslation("ui_text");

    // Callers often clear their title/description/confirmLabel source the
    // same tick they flip isOpen to false, but this dialog keeps rendering
    // through its ~150ms close animation. Freezing the last real content
    // avoids a flash of empty text during that exit transition.
    //
    // State, not a ref: React's "adjust state during render" pattern -
    // setShown re-renders immediately with the new value, then bails out
    // once it already matches, so it can't loop.
    const [shown, setShown] = useState({ title, description, confirmLabel });
    if (isOpen && (shown.title !== title || shown.description !== description || shown.confirmLabel !== confirmLabel)) {
        setShown({ title, description, confirmLabel });
    }

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onCancel()}>
            <DialogContent
                role="alertdialog"
                showCloseButton
                overlayClassName="backdrop-blur-[2px]"
                closeLabel={t("closeDialog")}
                returnFocusElement={returnFocusElement}
                // Use the same panel, header, and footer treatment as the
                // profile and access dialogs so confirmation dialogs do not
                // look like a separate card style.
                className={`${DIALOG_PANEL_CLASSNAME} w-[calc(100%-2rem)] min-w-0 max-w-md sm:w-fit`}
            >
                <DialogHeader className={DIALOG_HEADER_CLASSNAME}>
                    <DialogTitle className="text-xl tracking-[-0.02em]">{shown.title}</DialogTitle>
                </DialogHeader>
                <div className="bg-bg-canvas px-5 py-4 text-[15px] leading-6 text-fg-muted sm:px-6 sm:py-5">
                    {shown.description}
                    {onRetry && (
                        <Button className="mt-3" onClick={onRetry} variant="secondary" size="sm">
                            {retryLabel ?? t("retry")}
                        </Button>
                    )}
                </div>
                <DialogFooter className={DIALOG_FOOTER_CLASSNAME}>
                    <Button onClick={onCancel} disabled={isLoading} variant="secondary">
                        {t("cancel")}
                    </Button>
                    <Button
                        variant={isDestructive ? "destructive" : "brand"}
                        onClick={onConfirm}
                        loading={isLoading}
                        disabled={confirmDisabled || isLoading}
                    >
                        {shown.confirmLabel ?? t("confirm")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

export default ConfirmDialog;
