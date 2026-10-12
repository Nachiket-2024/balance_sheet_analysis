import React, { useState } from "react";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

import DetailsDrawer from "../../ui/display/DetailsDrawer";
import CollapsibleSection from "../../ui/display/CollapsibleSection";
import Badge from "../../ui/badges/Badge";
import { Button } from "../../ui/buttons/Button";
import type { AuthorizationAuditLogEntryRead } from "../../api/audit_api";
import type { SupportedLanguage } from "../../translations/translations";
import { formatTimestamp } from "../auditLogListConfig";
import { formatNumber } from "../../translations/numerals";
import { formatPolicyActionLabel, formatResourceTypeLabel } from "../../policies/policyCardHelpers";

interface AuthorizationDetailsDrawerProps {
    entry: AuthorizationAuditLogEntryRead | null;
    onClose: () => void;
    /** Position within the current filtered result set (1-based) and total row count, for the
     * "6 of 4,557" header. undefined while that count isn't known yet (still loading). */
    index: number | undefined;
    total: number | undefined;
    onPrevious: () => void;
    onNext: () => void;
    /** Whether prev/next can actually move right now - independent of index/total, since
     * those are the *global* filtered-result position (for display) while onPrevious/onNext
     * currently only move within the caller's already-loaded page of rows (see
     * AllAuthorizationLogSection's docstring on openRowIndex). Deriving these from
     * index<total would enable a Next button that does nothing on a page's last row.
     *
     * Deliberately scoped to one page, not extended to fetch the adjacent page at a boundary:
     * that would need a second in-flight query per drawer nav (racy with the table's own
     * paging/filter state, which can change while the drawer is open) for a rare case - PAGE_SIZE
     * is 25, so hitting a boundary means having already stepped through 24 rows in one sitting.
     * Prev/Next simply disable at the boundary instead (this prop), same as Pagination's own
     * disabled Prev on page 1 - a real limit, not a broken button. */
    canGoPrevious: boolean;
    canGoNext: boolean;
    language: SupportedLanguage;
    /** Footer one-click filter shortcuts - see AllAuthorizationLogSection's wiring. */
    onFilterUser?: (email: string) => void;
    onFilterAction?: (action: string) => void;
}

/**
 * Authorization decision detail sections (design/audit-log.html): Decision, Policies (granted-
 * by vs. considered-but-not-granting), Failed conditions (denials only), Request context
 * rendered as readable rows. Every field here already comes back from GET /authorization/audit-log - this only
 * lays it out, no extra fetch.
 */
function humanizeKey(key: string): string {
    const label = key.replace(/[_-]+/g, " ").trim();
    return label ? label.charAt(0).toUpperCase() + label.slice(1) : key;
}

function readableValue(value: unknown, language: SupportedLanguage): string {
    if (value === null || value === undefined) return "-";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (Array.isArray(value)) return value.length ? value.map((item) => readableValue(item, language)).join(", ") : "-";
    if (typeof value === "object") {
        return Object.entries(value as Record<string, unknown>)
            .map(([key, nestedValue]) => `${humanizeKey(key)}: ${readableValue(nestedValue, language)}`)
            .join("\n");
    }
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) {
        const timestamp = new Date(value);
        if (!Number.isNaN(timestamp.getTime())) return formatTimestamp(value, language);
    }
    return String(value);
}

const AuthorizationDetailsDrawer: React.FC<AuthorizationDetailsDrawerProps> = ({
    entry, onClose, index, total, onPrevious, onNext, canGoPrevious, canGoNext, language, onFilterUser, onFilterAction,
}) => {
    const { t } = useTranslation("audit_log");
    const [copiedField, setCopiedField] = useState<"user" | "event" | null>(null);

    if (!entry) return null;

    const copyField = (field: "user" | "event", value: string) => {
        navigator.clipboard.writeText(value);
        setCopiedField(field);
        setTimeout(() => setCopiedField(null), 1500);
    };

    const consideredNotGranting = entry.candidate_policy_names.filter(
        (name) => !entry.granting_policy_names.includes(name)
    );

    return (
        <DetailsDrawer
            isOpen={!!entry}
            onClose={onClose}
            title={t("authorization.drawer.title")}
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
                    {onFilterUser && (
                        <Button variant="outline" size="sm" onClick={() => onFilterUser(entry.user_email)}>
                            {t("authorization.drawer.onlyThisUser")}
                        </Button>
                    )}
                    {onFilterAction && (
                        <Button variant="outline" size="sm" onClick={() => onFilterAction(entry.action)}>
                            {t("authorization.drawer.onlyThisAction")}
                        </Button>
                    )}
                </>
            }
        >
            <CollapsibleSection staticOpen title={t("authorization.drawer.decision")}>
                <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                    <dt className="text-fg-muted">{t("authorization.columns.result")}</dt>
                    <dd>
                        {entry.allowed ? (
                            <Badge colorPalette="green" variant="subtle" size="sm">{t("authorization.results.allowed")}</Badge>
                        ) : (
                            <Badge colorPalette="red" size="sm">{t("authorization.results.denied")}</Badge>
                        )}
                    </dd>
                    <dt className="text-fg-muted">{t("authorization.columns.action")}</dt>
                    <dd className="min-w-0 break-words">{formatPolicyActionLabel(entry.action)}</dd>
                    <dt className="text-fg-muted">{t("authorization.columns.resource")}</dt>
                    <dd className="min-w-0 break-words">
                        <span>{formatResourceTypeLabel(entry.resource_type)}</span>
                        {entry.resource_identifier && <span className="text-fg-muted"> · {entry.resource_identifier}</span>}
                    </dd>
                    <dt className="text-fg-muted whitespace-nowrap">{t("authorization.columns.user")}</dt>
                    <dd className="flex min-w-0 items-start gap-2">
                        <span className="min-w-0 break-words">{entry.user_email}</span>
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="size-5"
                            onClick={() => copyField("user", entry.user_email)}
                            aria-label={copiedField === "user" ? t("authorization.drawer.copied") : t("authorization.drawer.copy")}
                        >
                            {copiedField === "user" ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
                        </Button>
                    </dd>
                    <dt className="text-fg-muted">{t("authorization.columns.when")}</dt>
                    <dd>{formatTimestamp(entry.created_at, language)}</dd>
                </dl>
            </CollapsibleSection>

            <CollapsibleSection staticOpen title={t("authorization.drawer.auditRecord")}>
                <dl>
                    <div className="flex min-w-0 items-start gap-3">
                        <dt className="shrink-0 text-fg-muted whitespace-nowrap">{t("authorization.drawer.eventId")}</dt>
                        <dd className="flex min-w-0 flex-1 items-start gap-2">
                            <span className="min-w-0 break-all">{entry.id}</span>
                        <Button
                            type="button"
                            variant="ghost"
                            size="icon-xs"
                            className="size-5"
                            onClick={() => copyField("event", String(entry.id))}
                            aria-label={copiedField === "event" ? t("authorization.drawer.copied") : t("authorization.drawer.copy")}
                        >
                            {copiedField === "event" ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
                        </Button>
                        </dd>
                    </div>
                </dl>
            </CollapsibleSection>

            <CollapsibleSection staticOpen title={t("authorization.drawer.policies")}>
                {entry.granting_policy_names.length === 0 && consideredNotGranting.length === 0 ? (
                    <p className="text-fg-muted">{t("authorization.drawer.noPoliciesConsidered")}</p>
                ) : (
                    <div className="flex flex-col gap-2">
                        {entry.granting_policy_names.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {entry.granting_policy_names.map((name) => (
                                    <Badge key={name} colorPalette="brand" size="sm">{name}</Badge>
                                ))}
                            </div>
                        )}
                        {consideredNotGranting.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                                {consideredNotGranting.map((name) => (
                                    <Badge key={name} colorPalette="gray" variant="outline" size="sm">{name}</Badge>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </CollapsibleSection>

            {!entry.allowed && (
                <CollapsibleSection staticOpen title={t("authorization.drawer.failedConditions")}>
                    {!entry.failed_conditions || Object.keys(entry.failed_conditions).length === 0 ? (
                        <p className="text-fg-muted">{t("authorization.drawer.noPolicyCovered")}</p>
                    ) : (
                        <ul className="flex flex-col gap-1.5 list-disc pl-4">
                            {Object.entries(entry.failed_conditions).map(([condition, needed]) => (
                                <li key={condition}>
                                    <span>{humanizeKey(condition)}</span>: {needed.join(", ")}
                                </li>
                            ))}
                        </ul>
                    )}
                </CollapsibleSection>
            )}

            {entry.context && Object.keys(entry.context).length > 0 && (
                <CollapsibleSection staticOpen title={t("authorization.drawer.requestContext")}>
                    <dl className="grid grid-cols-[max-content_minmax(0,1fr)] items-start gap-x-3 gap-y-2 [&>dt]:whitespace-nowrap">
                        {Object.entries(entry.context).map(([key, value]) => (
                            <React.Fragment key={key}>
                                <dt className="text-fg-muted">{humanizeKey(key)}</dt>
                                <dd className="min-w-0 whitespace-pre-wrap break-words">{readableValue(value, language)}</dd>
                            </React.Fragment>
                        ))}
                    </dl>
                </CollapsibleSection>
            )}
        </DetailsDrawer>
    );
};

export default AuthorizationDetailsDrawer;
