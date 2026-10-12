import React, { useState } from "react";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

import DetailsDrawer from "../../ui/display/DetailsDrawer";
import CollapsibleSection from "../../ui/display/CollapsibleSection";
import Badge from "../../ui/badges/Badge";
import { Button } from "../../ui/buttons/Button";
import type { SecurityAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";
import { formatNumber } from "../../translations/numerals";
import { securityAccessChangeDetails, securityAccessChangeSummary } from "./securityAccessChangeDetails";

interface SecurityDetailsDrawerProps {
    entry: SecurityAuditLogEntryRead | null;
    onClose: () => void;
    index: number | undefined;
    total: number | undefined;
    onPrevious: () => void;
    onNext: () => void;
    /** See AuthorizationDetailsDrawer's matching prop doc: independent of index/total, since
     * navigation currently only moves within the caller's already-loaded page of rows. */
    canGoPrevious: boolean;
    canGoNext: boolean;
    language: SupportedLanguage;
    onFilterUser?: (email: string) => void;
    onFilterIp?: (ip: string) => void;
    onFilterEvent?: (eventType: string) => void;
}

/**
 * Security event detail sections (design/audit-log.html): Event, Client (IP + user_agent),
 * Request (request id, event id), Metadata (readable labels, or a note when there is none). Every
 * field already comes back from GET /audit/security-log - this only lays it out.
 */
const METADATA_LABELS: Record<string, string> = {
    action: "Action",
    assigned_by: "Assigned by",
    changed_by: "Changed by",
    deleted_by: "Deleted by",
    granted_by: "Granted by",
    new_role: "New role",
    old_role: "Old role",
    policy_name: "Policy",
    purged_by: "Purged by",
    reactivated_by: "Reactivated by",
    reason: "Reason",
    resource_type: "Resource type",
    retained_actions: "Retained actions",
    revoked_by: "Revoked by",
    sessions_revoked: "Sessions revoked",
    sessions_revoked_confirmed: "Sessions revoked",
};

function metadataLabel(key: string): string {
    return METADATA_LABELS[key] ?? key
        .split("_")
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function metadataValue(value: unknown): string {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) {
        if (value.length === 0) return "-";
        return value.every((item) => ["string", "number", "boolean"].includes(typeof item))
            ? value.map(metadataValue).join(", ")
            : value.map(metadataValue).join("\n");
    }
    if (typeof value === "object") {
        return Object.entries(value as Record<string, unknown>)
            .map(([key, nestedValue]) => `${metadataLabel(key)}: ${metadataValue(nestedValue)}`)
            .join("\n");
    }
    return String(value);
}

function humanizeIdentifier(value: string): string {
    const label = value.replace(/[_-]+/g, " ").trim();
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : value;
}

const SecurityDetailsDrawer: React.FC<SecurityDetailsDrawerProps> = ({
    entry, onClose, index, total, onPrevious, onNext, canGoPrevious, canGoNext, language, onFilterUser, onFilterIp, onFilterEvent,
}) => {
    const { t } = useTranslation("audit_log");
    const [copiedField, setCopiedField] = useState<string | null>(null);

    if (!entry) return null;
    const accessChangeDetails = securityAccessChangeDetails(entry, t);
    const accessChangeSummary = securityAccessChangeSummary(entry, t);
    const metadataEntries = Object.entries(entry.event_metadata ?? {});

    const copy = (field: string, value: string) => {
        navigator.clipboard.writeText(value);
        setCopiedField(field);
        setTimeout(() => setCopiedField((f) => (f === field ? null : f)), 1500);
    };

    return (
        <DetailsDrawer
            isOpen={!!entry}
            onClose={onClose}
            title={t("security.drawer.title")}
            position={
                index !== undefined && total !== undefined
                    ? t("authorization.drawer.position", { index: formatNumber(index, language), total: formatNumber(total, language) })
                    : undefined
            }
            onPrevious={onPrevious}
            onNext={onNext}
            canGoPrevious={canGoPrevious}
            canGoNext={canGoNext}
            footer={
                <>
                    {onFilterUser && entry.user_email && (
                        <Button variant="outline" size="sm" onClick={() => onFilterUser(entry.user_email as string)}>
                            {t("security.drawer.onlyThisUser")}
                        </Button>
                    )}
                    {onFilterIp && entry.ip_address && (
                        <Button variant="outline" size="sm" onClick={() => onFilterIp(entry.ip_address as string)}>
                            {t("security.drawer.onlyThisIp")}
                        </Button>
                    )}
                    {onFilterEvent && (
                        <Button variant="outline" size="sm" onClick={() => onFilterEvent(entry.event_type)}>
                            {t("security.drawer.onlyThisEvent")}
                        </Button>
                    )}
                </>
            }
        >
            <CollapsibleSection staticOpen title={t("security.drawer.event")}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                    <dt className="text-fg-muted">{t("security.columns.result")}</dt>
                    <dd className="min-w-0">
                        {entry.success ? (
                            <Badge colorPalette="green" variant="subtle" size="sm">{t("security.results.success")}</Badge>
                        ) : (
                            <Badge colorPalette="red" size="sm">{t("security.results.failed")}</Badge>
                        )}
                    </dd>
                    <dt className="text-fg-muted">{t("security.columns.event")}</dt>
                    <dd className="min-w-0 break-words">{humanizeIdentifier(entry.event_type)}</dd>
                    <dt className="text-fg-muted">{t("security.columns.user")}</dt>
                    <dd className="min-w-0 break-words">{entry.user_email ?? <span className="text-fg-muted">{t("security.columns.unknownUser")}</span>}</dd>
                    <dt className="text-fg-muted">{t("security.columns.when")}</dt>
                    <dd className="min-w-0 break-words">{formatTimestamp(entry.created_at, language)}</dd>
                </dl>
            </CollapsibleSection>

            {accessChangeDetails.length > 0 && (
                <CollapsibleSection staticOpen title={t("security.drawer.accessChange")}>
                    {accessChangeSummary && <p className="mb-3 text-sm font-medium text-fg-default">{accessChangeSummary}</p>}
                    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                        {accessChangeDetails.map((detail) => (
                            <React.Fragment key={`${detail.label}:${detail.value}`}>
                                <dt className="text-fg-muted">{detail.label}</dt>
                                <dd className="min-w-0 break-words">{detail.value}</dd>
                            </React.Fragment>
                        ))}
                        <dt className="text-fg-muted">{t("security.columns.when")}</dt>
                        <dd className="min-w-0 break-words">{formatTimestamp(entry.created_at, language)}</dd>
                    </dl>
                </CollapsibleSection>
            )}

            <CollapsibleSection staticOpen title={t("security.drawer.client")}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                    <dt className="text-fg-muted">{t("security.columns.ip")}</dt>
                    <dd className="flex min-w-0 flex-wrap items-start gap-2">
                        <span className="min-w-0 break-words">{entry.ip_address ?? t("security.columns.unknownIp")}</span>
                        {entry.ip_address && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon-xs"
                                className="size-5"
                                onClick={() => copy("ip", entry.ip_address as string)}
                                aria-label={copiedField === "ip" ? t("authorization.drawer.copied") : t("authorization.drawer.copy")}
                            >
                                {copiedField === "ip" ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
                            </Button>
                        )}
                    </dd>
                    <dt className="text-fg-muted">{t("security.drawer.userAgent")}</dt>
                    <dd className="min-w-0 break-words">
                        {entry.user_agent ?? <span className="text-fg-muted">{t("security.drawer.noUserAgent")}</span>}
                    </dd>
                </dl>
            </CollapsibleSection>

            <CollapsibleSection staticOpen title={t("security.drawer.request")}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                    <dt className="text-fg-muted">{t("security.drawer.requestId")}</dt>
                    <dd className="min-w-0 break-words">
                        {entry.request_id ?? <span className="text-fg-muted">{t("security.drawer.noRequestId")}</span>}
                    </dd>
                    <dt className="text-fg-muted">{t("security.drawer.eventId")}</dt>
                    <dd className="min-w-0 break-words">{entry.id}</dd>
                </dl>
            </CollapsibleSection>

            <CollapsibleSection staticOpen title={t("security.drawer.metadata")}>
                {metadataEntries.length > 0 ? (
                    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                        {metadataEntries.map(([key, value]) => (
                            <React.Fragment key={key}>
                                <dt className="text-fg-muted">{metadataLabel(key)}</dt>
                                <dd className="min-w-0 whitespace-pre-wrap break-words">{metadataValue(value)}</dd>
                            </React.Fragment>
                        ))}
                    </dl>
                ) : (
                    <p className="text-fg-muted">{t("security.drawer.noMetadata")}</p>
                )}
            </CollapsibleSection>
        </DetailsDrawer>
    );
};

export default SecurityDetailsDrawer;
