import React, { useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Sheet, SheetContent, SheetHeader, SheetTitle } from "../shadcn/sheet";
import { Button } from "../buttons/Button";

interface DetailsDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    /** "6 of 4,557" position indicator, already formatted by the caller (locale-aware
     * thousands separators, see auditLogListConfig's formatNumber usage elsewhere). */
    position?: string;
    onPrevious?: () => void;
    onNext?: () => void;
    canGoPrevious?: boolean;
    canGoNext?: boolean;
    /** Section content (a list of CollapsibleSection elements). */
    children: React.ReactNode;
    /** Rendered as a footer row below the sections (one-click filter shortcuts). */
    footer?: React.ReactNode;
}

/**
 * Right-side drawer shell shared by the Authorization/Security details drawers: a row's
 * details on row click, with keyboard prev/next (j/k, matching Gmail/Linear's list-navigation
 * convention) alongside visible buttons, and Esc to close (Sheet's underlying Radix Dialog
 * already handles Esc on its own). Section content is the caller's job (AuthorizationDetails
 * Drawer/SecurityDetailsDrawer each build their own CollapsibleSection list) - this owns only
 * the header/position/footer chrome common to both.
 */
const DetailsDrawer: React.FC<DetailsDrawerProps> = ({
    isOpen, onClose, title, position, onPrevious, onNext, canGoPrevious, canGoNext, children, footer,
}) => {
    const { t } = useTranslation("ui_text");

    useEffect(() => {
        if (!isOpen) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            const target = e.target as HTMLElement;
            // Never hijack navigation while the user is typing in a field or editing text
            // inside the drawer. Buttons remain navigable with arrows because the drawer's
            // previous/next controls are themselves directional controls.
            if (
                target.tagName === "INPUT" ||
                target.tagName === "TEXTAREA" ||
                target.tagName === "SELECT" ||
                target.isContentEditable
            ) return;
            if ((e.key === "j" || e.key === "ArrowRight" || e.key === "ArrowDown") && canGoNext) {
                e.preventDefault();
                onNext?.();
            } else if ((e.key === "k" || e.key === "ArrowLeft" || e.key === "ArrowUp") && canGoPrevious) {
                e.preventDefault();
                onPrevious?.();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, onNext, onPrevious, canGoNext, canGoPrevious]);

    return (
        <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <SheetContent closeLabel={t("closeDialog")}>
                <SheetHeader>
                    <div className="flex items-center justify-between gap-2">
                        <SheetTitle>{title}</SheetTitle>
                    </div>
                    {(position || onPrevious || onNext) && (
                        <div className="flex items-center gap-2">
                            {position && <span className="text-sm text-fg-muted">{position}</span>}
                            <div className="flex items-center gap-1 ml-auto">
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    aria-label={t("previous")}
                                    disabled={!canGoPrevious}
                                    onClick={onPrevious}
                                >
                                    <ChevronLeft size={16} aria-hidden="true" />
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="icon-sm"
                                    aria-label={t("next")}
                                    disabled={!canGoNext}
                                    onClick={onNext}
                                >
                                    <ChevronRight size={16} aria-hidden="true" />
                                </Button>
                            </div>
                        </div>
                    )}
                </SheetHeader>

                <div className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden px-4 py-4 sm:px-6 flex flex-col gap-3 bg-bg-canvas [scrollbar-gutter:stable]">{children}</div>

                {footer && <div className="min-w-0 border-t border-brand-border px-4 py-3 sm:px-6 flex items-center gap-2 flex-wrap bg-bg-canvas">{footer}</div>}
            </SheetContent>
        </Sheet>
    );
};

export default DetailsDrawer;
