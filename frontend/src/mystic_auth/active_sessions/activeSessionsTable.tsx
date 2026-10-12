/* eslint-disable react-refresh/only-export-components -- this feature module owns both the table renderer and its column factory. */
import React from "react";
import { Laptop, Smartphone, Tablet } from "lucide-react";

import AppTooltip from "../ui/feedback/AppTooltip";
import Badge from "../ui/badges/Badge";
import type { DataTableColumn } from "../ui/DataTable/DataTable";
import TableActionButton from "../ui/table_actions/TableActionButton";
import { DESTRUCTIVE_TABLE_ACTION_CLASSNAME } from "../ui/table_actions/tableActionPalettes";
import { formatDateTime, formatRelativeTime } from "../ui/dates/dateFormatters";
import { deviceCategoryFor, parseUserAgent } from "./parseUserAgent";
import type { SessionRead } from "../api/auth_api";
import type { SupportedLanguage } from "../translations/translations";

type Translate = (key: string, options?: Record<string, unknown>) => string;

const TwoLineCell: React.FC<{ primary: string; secondary?: string }> = ({ primary, secondary }) => (
    <div className="overflow-hidden">
        <p className="text-sm font-medium truncate" title={primary}>{primary}</p>
        {secondary && <p className="text-[13px] leading-tight text-fg-muted truncate" title={secondary}>{secondary}</p>}
    </div>
);

const DEVICE_ICONS = { desktop: Laptop, mobile: Smartphone, tablet: Tablet };

const DeviceIcon: React.FC<{ userAgent: string | null }> = ({ userAgent }) => {
    const Icon = DEVICE_ICONS[deviceCategoryFor(userAgent)];
    return <div className="grid size-9 shrink-0 place-items-center text-fg-muted"><Icon size={20} aria-hidden="true" /></div>;
};

const MissingValue: React.FC<{ label: string }> = ({ label }) => (
    <AppTooltip content={label}>
        <span className="text-sm text-fg-subtle cursor-default"><span aria-hidden="true">–</span><span className="sr-only">{label}</span></span>
    </AppTooltip>
);

interface ActiveSessionTableOptions {
    t: Translate;
    language: SupportedLanguage;
    now: number;
    onEnd: (session: SessionRead) => void;
    currentLogoutPending: boolean;
    revokePending: boolean;
    revokeId: number | undefined;
}

export function createActiveSessionColumns({
    t,
    language,
    now,
    onEnd,
    currentLogoutPending,
    revokePending,
    revokeId,
}: ActiveSessionTableOptions): DataTableColumn<SessionRead>[] {
    return [
        {
            key: "device",
            header: t("activeSessionsCard.deviceColumn"),
            width: "11.5rem",
            render: (session) => {
                const label = parseUserAgent(session.user_agent);
                return <div className="flex items-center gap-2.5 min-w-0">
                    <DeviceIcon userAgent={session.user_agent} />
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <AppTooltip content={label}><p className="text-sm font-medium truncate">{label}</p></AppTooltip>
                        {session.is_current && <Badge colorPalette="brand" variant="subtle" size="sm">{t("activeSessionsCard.thisDeviceBadge")}</Badge>}
                    </div>
                </div>;
            },
        },
        {
            key: "location",
            header: t("activeSessionsCard.locationColumn"),
            width: "7rem",
            render: (session) => {
                if (session.city && session.country) return <TwoLineCell primary={session.city} secondary={session.country} />;
                const place = session.city ?? session.country;
                return place ? <TwoLineCell primary={place} /> : <MissingValue label={t("activeSessionsCard.locationUnavailable")} />;
            },
        },
        {
            key: "ip_address",
            header: t("activeSessionsCard.ipColumn"),
            width: "8rem",
            render: (session) => session.ip_address ? <p className="text-sm text-fg-muted">{session.ip_address}</p> : <MissingValue label={t("activeSessionsCard.ipUnavailable")} />,
        },
        {
            key: "created_at",
            header: t("activeSessionsCard.signedInColumn"),
            width: "9.5rem",
            render: (session) => <TwoLineCell primary={formatRelativeTime(session.created_at, language, now)} secondary={formatDateTime(session.created_at, language)} />,
        },
        {
            key: "last_used_at",
            header: t("activeSessionsCard.lastSeenColumn"),
            width: "9.5rem",
            render: (session) => <TwoLineCell primary={formatRelativeTime(session.last_used_at, language, now)} secondary={formatDateTime(session.last_used_at, language)} />,
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            width: "6rem",
            render: (session) => <TableActionButton
                colorPalette="red"
                className={DESTRUCTIVE_TABLE_ACTION_CLASSNAME}
                onClick={() => onEnd(session)}
                loading={(session.is_current && currentLogoutPending) || (!session.is_current && revokePending && revokeId === session.id)}
            >
                {t("activeSessionsCard.logOut")}
            </TableActionButton>,
        },
    ];
}
