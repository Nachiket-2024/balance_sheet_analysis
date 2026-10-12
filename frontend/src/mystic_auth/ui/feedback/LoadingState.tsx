import React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "../styles/classNames";

interface LoadingStateProps {
    message: string;
    // When true, fills the viewport for whole-page loading gates. When
    // false, sizes to its container (e.g. a card body).
    fullScreen?: boolean;
}

/** Single consistent loading treatment, replacing three near-duplicate
 * local components that had each drifted to a slightly different spinner color. */
const LoadingState: React.FC<LoadingStateProps> = ({ message, fullScreen = false }) => {
    return (
        <div
            className={cn(
                "flex items-center justify-center",
                fullScreen ? "h-screen bg-bg-canvas" : "h-full py-12"
            )}
        >
            <div className="flex items-center">
                <Loader2 className="size-8 animate-spin text-brand-solid" aria-hidden="true" />
                <span className="ml-4 text-lg text-fg-muted">{message}</span>
            </div>
        </div>
    );
};

export default LoadingState;
