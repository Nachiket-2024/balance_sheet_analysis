import React, { useState } from "react";
import { Link as LinkIcon, Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../buttons/Button";
import AppTooltip from "../feedback/AppTooltip";

interface CopyLinkButtonProps {
    /** Returns the query params (category/scope/filters/sort/page - whatever the caller's view
     * state is) that make this exact view reopenable. Called at click time, not on every
     * render, so it can read the very latest state without re-rendering the button itself. */
    buildParams: () => Record<string, string>;
    className?: string;
}

/**
 * "Copy link to this view" (design/audit-log.html's page-header button): builds a URL from the
 * current page path plus the caller's params and writes it to the clipboard. Flips to a
 * checkmark for 1.5s on success, same transient-feedback pattern as the details drawer's own
 * Copy buttons (AuthorizationDetailsDrawer.tsx) rather than a toast.
 */
const CopyLinkButton: React.FC<CopyLinkButtonProps> = ({ buildParams, className }) => {
    const { t } = useTranslation("audit_log");
    const [copied, setCopied] = useState(false);

    const handleClick = () => {
        const params = new URLSearchParams(buildParams());
        const url = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
        void navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
    };

    return (
        <AppTooltip content={t("shared.copyLinkTooltip")}>
            <Button type="button" variant="outline" size="sm" onClick={handleClick} className={className}>
                {copied ? <Check size={14} aria-hidden="true" /> : <LinkIcon size={14} aria-hidden="true" />}
                {t("shared.copyLinkToView")}
            </Button>
        </AppTooltip>
    );
};

export default CopyLinkButton;
