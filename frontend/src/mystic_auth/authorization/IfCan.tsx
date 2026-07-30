import React, { type ReactNode } from "react";

import { Authorized } from "./Authorized";

interface IfCanProps {
    action: string;
    resourceType?: string;
    fallback?: ReactNode;
    children: ReactNode;
}

/**
 * Alias of Authorized, named for call sites that read more naturally as "if the user can do
 * this action" than "if authorized for this permission". Reuses Authorized directly rather than
 * duplicating its logic under a differently-named prop.
 */
export const IfCan: React.FC<IfCanProps> = ({ action, resourceType, fallback, children }) => (
    <Authorized permission={action} resourceType={resourceType} fallback={fallback}>
        {children}
    </Authorized>
);
