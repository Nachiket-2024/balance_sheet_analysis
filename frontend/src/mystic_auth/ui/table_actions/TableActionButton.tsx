import React from "react";

import { Button, type ButtonProps } from "../buttons/Button";
import { cn } from "../styles/classNames";
import { TABLE_ACTION_PALETTE_STYLES } from "./tableActionPalettes";

/**
 * Per-row table action button (Edit, Policies, Delete, ...). Deliberately
 * higher-contrast, fixed palette values instead of Button's own variants:
 * these need per-action colors (destructive/reactivate/deactivate/...) that
 * don't map to Button's fixed variant set.
 */
type TableActionButtonProps = Omit<ButtonProps, "variant"> & {
    colorPalette: keyof typeof TABLE_ACTION_PALETTE_STYLES;
};

const TableActionButton: React.FC<TableActionButtonProps> = ({ colorPalette, size = "xs", className, ...rest }) => {
    return (
        <Button
            variant="ghost"
            size={size}
            // xs's stock text size is 12px - a bit small for how often these
            // get read and clicked across every table. Bumped once here so
            // every row-action button gets it uniformly.
            className={cn("text-sm transition-colors", TABLE_ACTION_PALETTE_STYLES[colorPalette], className)}
            {...rest}
        />
    );
};

export default TableActionButton;
