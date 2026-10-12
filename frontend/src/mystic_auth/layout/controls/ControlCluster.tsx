import React from "react";

import FontSizeControl from "./FontSizeControl";
import LanguageToggle from "./LanguageToggle";
import ThemeToggle from "./ThemeToggle";

/**
 * Font size / language / theme toggles - three separately-boxed, neutral
 * buttons (Button's "icon"/"icon-sm" variant, matching the command-palette
 * search trigger's look), shared by Navbar, AuthLayout and LandingPage. A
 * shared-border segmented version was tried and reverted back to this
 * standalone layout.
 */
const ControlCluster: React.FC = () => (
    <div
        aria-label="Display preferences"
        className="flex items-center gap-1 rounded-xl border border-border-card/80 bg-bg-surface/85 p-1 shadow-card backdrop-blur-md"
    >
        <FontSizeControl />
        <LanguageToggle />
        <ThemeToggle />
    </div>
);

export default ControlCluster;
