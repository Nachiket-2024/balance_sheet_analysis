import React from "react";
import { CircleCheck, CircleX, TriangleAlert } from "lucide-react";

import { Alert, AlertTitle } from "../shadcn/alert";
import { cn } from "../styles/classNames";

interface FormAlertProps {
    // "warning" backs the "primary action succeeded, but a secondary
    // side-effect didn't" case (e.g. password-reset-confirm's
    // sessions_revoked: false), distinct from "error" and "success".
    status: "error" | "success" | "warning";
    // Lets a caller point a field's aria-describedby at this alert, so a
    // screen reader announces the error in context with the input it concerns.
    id?: string;
    /** Defaults to "md" so every existing caller keeps its current text
     * size unchanged; pass "lg" where a surrounding page has standardized
     * on nothing smaller than that. */
    size?: "sm" | "md" | "lg";
    children: React.ReactNode;
}

const STATUS_ICON = { error: CircleX, success: CircleCheck, warning: TriangleAlert };

// shadcn's Alert only ships "default"/"destructive" variants, with no
// built-in status->color mapping, so error/warning/success colors
// (red/green/orange) are applied here directly instead.
const STATUS_CLASSES = {
    error: "border-red-300 bg-red-50 text-red-800 dark:border-red-700 dark:bg-red-950 dark:text-red-200 [&>svg]:text-red-600 dark:[&>svg]:text-red-400",
    success: "border-green-300 bg-green-50 text-green-800 dark:border-green-700 dark:bg-green-950 dark:text-green-200 [&>svg]:text-green-600 dark:[&>svg]:text-green-400",
    warning: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-700 dark:bg-orange-950 dark:text-orange-200 [&>svg]:text-orange-600 dark:[&>svg]:text-orange-400",
};

const SIZE_CLASSES = { sm: "text-xs [&>svg]:size-3.5", md: "text-sm", lg: "text-base [&>svg]:size-5" };

/**
 * Replaces the ad hoc `<Text color="red.500">` / `<Text color="green.500">`
 * pattern repeated across every auth form. shadcn's Alert already renders
 * role="alert" (see ui/shadcn/alert.tsx), so screen readers announce this
 * content when it appears without needing to set the role here.
 */
const FormAlert: React.FC<FormAlertProps> = ({ status, id, size = "md", children }) => {
    const Icon = STATUS_ICON[status];
    return (
        <Alert id={id} className={cn(STATUS_CLASSES[status], SIZE_CLASSES[size])}>
            <Icon />
            <AlertTitle>{children}</AlertTitle>
        </Alert>
    );
};

export default FormAlert;
