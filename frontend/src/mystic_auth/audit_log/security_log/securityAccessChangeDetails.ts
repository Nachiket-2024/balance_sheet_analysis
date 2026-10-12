import type { TFunction } from "i18next";

import type { SecurityAuditLogEntryRead } from "../../api/audit_api";

export interface SecurityAccessChangeDetail {
    label: string;
    value: string;
}

function stringValue(value: unknown): string | null {
    return typeof value === "string" && value.trim() ? value : null;
}

export function securityAccessChangeSummary(
    entry: SecurityAuditLogEntryRead,
    t: TFunction<"audit_log">
): string | null {
    const details = securityAccessChangeDetails(entry, t);
    if (details.length === 0) return null;

    switch (entry.event_type) {
        case "policy_assigned":
            return t("security.details.policyAssigned", {
                policyName: stringValue(entry.event_metadata?.policy_name) ?? "-",
                actor: stringValue(entry.event_metadata?.assigned_by) ?? "-",
            });
        case "policy_revoked":
            return t("security.details.policyRevoked", {
                policyName: stringValue(entry.event_metadata?.policy_name) ?? "-",
                actor: stringValue(entry.event_metadata?.revoked_by) ?? "-",
            });
        case "policy_action_revoked":
            return t("security.details.policyActionRevoked", {
                action: stringValue(entry.event_metadata?.action) ?? "-",
                policyName: stringValue(entry.event_metadata?.policy_name) ?? "-",
                actor: stringValue(entry.event_metadata?.revoked_by) ?? "-",
            });
        case "permission_granted":
            return t("security.details.permissionGranted", {
                action: stringValue(entry.event_metadata?.action) ?? "-",
                resourceType: stringValue(entry.event_metadata?.resource_type) ?? "-",
                actor: stringValue(entry.event_metadata?.granted_by) ?? "-",
            });
        case "permission_revoked":
            return t("security.details.permissionRevoked", {
                action: stringValue(entry.event_metadata?.action) ?? "-",
                resourceType: stringValue(entry.event_metadata?.resource_type) ?? "-",
                actor: stringValue(entry.event_metadata?.revoked_by) ?? "-",
            });
        case "user_role_changed":
            return t("security.details.roleChanged", {
                oldRole: stringValue(entry.event_metadata?.old_role) ?? "-",
                newRole: stringValue(entry.event_metadata?.new_role) ?? "-",
                actor: stringValue(entry.event_metadata?.changed_by) ?? "-",
            });
        default:
            return null;
    }
}

export function securityAccessChangeDetails(
    entry: SecurityAuditLogEntryRead,
    t: TFunction<"audit_log">
): SecurityAccessChangeDetail[] {
    const m = entry.event_metadata;
    if (!m) return [];

    const target = entry.user_email ? [{ label: t("security.drawer.targetUser"), value: entry.user_email }] : [];
    const actor = (key: "assigned_by" | "revoked_by" | "granted_by" | "changed_by") => {
        const value = stringValue(m[key]);
        return value ? [{ label: t("security.drawer.actor"), value }] : [];
    };
    const field = (label: string, key: string) => {
        const value = stringValue(m[key]);
        return value ? [{ label, value }] : [];
    };

    switch (entry.event_type) {
        case "policy_assigned":
            return [...target, ...actor("assigned_by"), ...field(t("security.drawer.policy"), "policy_name")];
        case "policy_revoked":
            return [...target, ...actor("revoked_by"), ...field(t("security.drawer.policy"), "policy_name")];
        case "policy_action_revoked":
            return [
                ...target,
                ...actor("revoked_by"),
                ...field(t("security.drawer.policy"), "policy_name"),
                ...field(t("security.drawer.action"), "action"),
            ];
        case "permission_granted":
            return [
                ...target,
                ...actor("granted_by"),
                ...field(t("security.drawer.action"), "action"),
                ...field(t("security.drawer.resourceType"), "resource_type"),
            ];
        case "permission_revoked":
            return [
                ...target,
                ...actor("revoked_by"),
                ...field(t("security.drawer.action"), "action"),
                ...field(t("security.drawer.resourceType"), "resource_type"),
            ];
        case "user_role_changed":
            return [
                ...target,
                ...actor("changed_by"),
                ...field(t("security.drawer.oldRole"), "old_role"),
                ...field(t("security.drawer.newRole"), "new_role"),
            ];
        default:
            return [];
    }
}
