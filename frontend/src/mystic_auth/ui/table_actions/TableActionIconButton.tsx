import React from "react";

import AppTooltip from "../feedback/AppTooltip";
import { Button, type ButtonProps } from "../buttons/Button";
import { cn } from "../styles/classNames";
import { TABLE_ACTION_PALETTE_STYLES } from "./tableActionPalettes";

type TableActionIconButtonProps = Omit<ButtonProps, "variant" | "size" | "aria-label"> & {
    colorPalette: keyof typeof TABLE_ACTION_PALETTE_STYLES;
    /** Used as both the button's aria-label and its hover/focus tooltip text,
     * so a row of icon-only actions stays identifiable to screen-reader and
     * sighted users alike without needing a visible text label. */
    label: string;
    /** Overrides the tooltip text while `disabled` is true, e.g. "The
     * reserved system account cannot be modified", so a disabled action
     * explains itself on hover/focus. Deliberately does NOT change the
     * button's aria-label: callers select these by their stable accessible
     * name regardless of disabled state, and screen readers already
     * announce "disabled" from the native attribute. Ignored while enabled. */
    disabledLabel?: string;
};

/**
 * Icon-only counterpart to TableActionButton, for rows where several actions
 * must always stay on one line regardless of locale - translated labels vary
 * too widely in width (e.g. "Purge" vs. "स्थायी रूप से हटाएं") for text
 * buttons to guarantee that. Reuses the same palette styling so icon and
 * text row-actions read as one design language.
 */
const TableActionIconButton: React.FC<TableActionIconButtonProps> = ({ colorPalette, label, disabledLabel, className, ...rest }) => {
    // Read (without removing) `disabled` off `rest` so it still flows to
    // Button via the same `...rest` spread.
    const tooltipText = rest.disabled && disabledLabel ? disabledLabel : label;

    return (
        <AppTooltip content={tooltipText}>
            <Button
                variant="ghost"
                size="icon-sm"
                aria-label={label}
                className={cn("transition-colors", TABLE_ACTION_PALETTE_STYLES[colorPalette], className)}
                {...rest}
            />
        </AppTooltip>
    );
};

export default TableActionIconButton;
