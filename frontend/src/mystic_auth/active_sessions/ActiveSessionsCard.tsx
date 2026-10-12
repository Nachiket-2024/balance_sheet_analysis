import React, { useEffect, useState } from "react";
import { LogOut, MonitorOff, MonitorSmartphone, MousePointerClick, X } from "lucide-react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";

import AppTooltip from "../ui/feedback/AppTooltip";
import Badge from "../ui/badges/Badge";
import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import DataTable from "../ui/DataTable/DataTable";
import TableActionButton from "../ui/table_actions/TableActionButton";
import ConfirmDialog from "../ui/feedback/ConfirmDialog";
import FormAlert from "../ui/feedback/FormAlert";
import { Button } from "../ui/buttons/Button";
import { toaster } from "../ui/toaster/toasterInstance";
import { useLogoutMutation } from "../auth/logout/useLogoutMutation";
import { useLogoutAllMutation } from "../auth/logout_all/useLogoutAllMutation";
import { useLanguageStore } from "../store/languageStore";
import { useNow } from "../ui/hooks/useNow";
import { formatNumber } from "../translations/numerals";
import { parseUserAgent } from "./parseUserAgent";
import { useSessionsQuery } from "./useSessionsQuery";
import { useRevokeSessionMutation, useBulkRevokeSessionsMutation } from "./useRevokeSessionMutation";
import type { SessionRead } from "../api/auth_api";
import { createActiveSessionColumns } from "./activeSessionsTable";
import { DESTRUCTIVE_TABLE_ACTION_CLASSNAME } from "../ui/table_actions/tableActionPalettes";

/**
 * ActiveSessionsCard
 * ----------------------------
 * Lists the caller's own active login sessions (GET /auth/sessions) as a
 * table (device/browser, location, IP address, first-signed-in, last-seen,
 * an action column), same shape as every other management list in the app.
 * Every row gets a working "Log out", including the current device's row ("This device"
 * badge): that one goes through the ordinary single-device logout
 * (POST /auth/logout, same as the navbar's Logout button) instead of
 * DELETE /auth/sessions/{id}, because the backend rejects revoking your own
 * current session that way (it would invalidate the request doing it).
 *
 * Lives in its own top-level `active_sessions/` feature folder (mirroring
 * the backend's `auth/active_sessions/` + `user_session/`), not under
 * `dashboard/`: this is session-management domain logic that happens to
 * render on DashboardPage.tsx, not owned by it. It's the sole place to
 * manage sessions - Account Settings no longer duplicates it on its own
 * tab, and Dashboard's identity card only shows an Active Sessions *count*,
 * from the same underlying data, as one of its own stat tiles.
 *
 * Also owns "Log out everywhere" (POST /auth/logout-all): ends every active
 * session, including the caller's own, and redirects to /login - distinct
 * from "Log out selected" below, which bulk-revokes chosen OTHER sessions
 * and can never touch "This device" (see disabledSessionKeys below). Both
 * live on this one card now, rather than splitting "end some sessions" here
 * and "end all of them" as a separate Dashboard quick action: every way to
 * end a session belongs together.
 */

const ActiveSessionsCard: React.FC<React.ComponentPropsWithoutRef<"div">> = ({ ...cardProps }) => {
    const { t } = useTranslation("dashboard");
    // See AllAuthorizationLogSection.tsx's matching comment: dates use
    // chromeLanguage, not pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const { data: sessions, isLoading, isError } = useSessionsQuery();
    const now = useNow(30_000);
    const [endingSession, setEndingSession] = useState<SessionRead | null>(null);
    const revokeMutation = useRevokeSessionMutation();
    const logoutMutation = useLogoutMutation();
    const logoutAllMutation = useLogoutAllMutation();
    const [logoutAllConfirmOpen, setLogoutAllConfirmOpen] = useState(false);
    const navigate = useNavigate();

    // Selection for the bulk "Log out selected" action below the table,
    // same DataTable selectable/selectedKeys/onSelectionChange wiring as
    // UsersPage's bulk toolbar. The current device's session is passed as a
    // `disabledKeys` entry (never checkable, excluded from "select all"),
    // since revoking it via the bulk path hits the same
    // CANNOT_REVOKE_CURRENT_SESSION 400 as a single revoke would (see
    // session_revoke_handler.py).
    const [selectedSessionIds, setSelectedSessionIds] = useState<ReadonlySet<string | number>>(new Set());
    const currentSessionId = sessions?.find((s) => s.is_current)?.id;
    const disabledSessionKeys = new Set<string | number>(currentSessionId !== undefined ? [currentSessionId] : []);
    // "Select mode" toggle, same as UsersPage's BulkActionToolbar: off by
    // default so a plain click still selects/copies cell text.
    const [rowClickSelects, setRowClickSelects] = useState(false);
    const [bulkEnding, setBulkEnding] = useState(false);
    const bulkRevokeMutation = useBulkRevokeSessionsMutation();

    // ConfirmDialog keeps rendering (mid closing-animation) for a beat after
    // endingSession is cleared to null, so its title/description must keep
    // reading off the last real session, not endingSession directly, or the
    // is_current ternary flips to the other copy for that last frame and
    // flashes the wrong text right before the dialog closes. Derived-during-
    // render state (not a ref, since react-hooks/refs forbids reading or
    // writing ref.current during render), matching React's own pattern for
    // storing info from previous renders.
    const [lastEndingSession, setLastEndingSession] = useState<SessionRead | null>(null);
    if (endingSession && endingSession !== lastEndingSession) setLastEndingSession(endingSession);
    const dialogSession = endingSession ?? lastEndingSession;

    // isSuccess OR isError: useLogoutMutation clears local auth state in
    // onSettled regardless of outcome (a NO_REFRESH_TOKEN_COOKIE 400 is a
    // real, reachable response), so navigation must follow every settled
    // mutation, or ending "This device"'s row leaves the user stuck on this
    // now-stale page instead of redirecting to /login.
    useEffect(() => {
        if (logoutMutation.isSuccess || logoutMutation.isError) navigate("/login");
    }, [logoutMutation.isSuccess, logoutMutation.isError, navigate]);

    // Same isSuccess-OR-isError reasoning as the single-device logout above:
    // useLogoutAllMutation clears local auth state in onSettled regardless of
    // outcome, so navigation must follow every settled mutation or a failed
    // call leaves the user stuck on this now-stale page. This used to live on
    // DashboardPage as its own "Logout All" quick action; it moved here so
    // every way to end a session (one, several, or all of them) lives on this
    // one card instead of being split across two pages.
    useEffect(() => {
        if (logoutAllMutation.isSuccess || logoutAllMutation.isError) navigate("/login");
    }, [logoutAllMutation.isSuccess, logoutAllMutation.isError, navigate]);

    const handleConfirm = () => {
        if (!endingSession) return;

        if (endingSession.is_current) {
            logoutMutation.mutate();
            setEndingSession(null);
            return;
        }

        revokeMutation.mutate(endingSession.id, {
            onSuccess: () => {
                toaster.create({ title: t("activeSessionsCard.sessionEndedToast"), type: "success" });
                setEndingSession(null);
            },
            onError: (error) => {
                toaster.create({ title: error.message, type: "error" });
                setEndingSession(null);
            },
        });
    };

    const handleBulkConfirm = () => {
        bulkRevokeMutation.mutate([...selectedSessionIds] as number[], {
            onSuccess: (results) => {
                const errorCount = results.filter((r) => r.status === "error").length;
                const successCount = results.length - errorCount;
                toaster.create({
                    title:
                        errorCount === 0
                            ? t("activeSessionsCard.bulkEndSuccessToast", { count: successCount })
                            : t("activeSessionsCard.bulkEndPartialToast", { success: successCount, error: errorCount }),
                    type: errorCount === 0 ? "success" : "warning",
                });
                setSelectedSessionIds(new Set());
                setBulkEnding(false);
            },
        });
    };

    const columns = createActiveSessionColumns({
        t,
        language,
        now,
        onEnd: setEndingSession,
        currentLogoutPending: logoutMutation.isPending,
        revokePending: revokeMutation.isPending,
        revokeId: revokeMutation.variables,
    });

    return (
        <Card {...cardProps}>
            {/* Title and "Log out everywhere" as direct space-between
                siblings (design/dashboard.html's `.session-toolbar`) - an
                earlier version grouped them together in one left-aligned
                flex row, with the "this device isn't selectable" hint
                stranded on the right instead, which put the wrong two
                things next to each other. */}
            <div className="flex items-center justify-between gap-2 mb-4 flex-wrap">
                <div className="flex items-center gap-2">
                    <SectionHeading className="flex items-center gap-2">
                        <MonitorSmartphone size={17} aria-hidden="true" color="var(--brand-solid)" />
                        {t("activeSessionsCard.heading")}
                    </SectionHeading>
                    {/* Count beside the heading, not inside it, so the
                        heading's accessible name stays "Active Sessions".
                        Screen readers get the full phrase instead of a bare
                        number. */}
                    {sessions && (
                        <>
                            <Badge colorPalette="brand" variant="subtle" size="sm" className="rounded-full" aria-hidden="true">
                                {formatNumber(sessions.length, language)}
                            </Badge>
                            <span className="sr-only">{t("activeSessionsCard.sessionCount", { count: sessions.length })}</span>
                        </>
                    )}
                </div>
                <TableActionButton
                    size="sm"
                    colorPalette="red"
                    className={DESTRUCTIVE_TABLE_ACTION_CLASSNAME}
                    loading={logoutAllMutation.isPending}
                    onClick={() => setLogoutAllConfirmOpen(true)}
                >
                    <LogOut size={14} aria-hidden="true" /> {t("activeSessionsCard.logOutEverywhereButton")}
                </TableActionButton>
            </div>

            {logoutAllMutation.isError && (
                <FormAlert status="error">{logoutAllMutation.error.message}</FormAlert>
            )}

            {sessions && sessions.length > 1 && (
                <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                    {/* Two separate spans (design/dashboard.html's two
                        `.session-hint` spans), not one concatenated string -
                        keeps "N selected" on its own as real, separately
                        findable text instead of merging it into a longer
                        sentence. */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-sm text-fg-muted">
                            {t("ui_text:selectedCount", { count: selectedSessionIds.size })}
                        </span>
                        <span className="text-sm text-fg-muted">
                            {"· " + t("activeSessionsCard.thisDeviceNotSelectable")}
                        </span>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        <AppTooltip content={t("activeSessionsCard.rowClickSelectTitle")}>
                            {/* Same solid brand fill as ChangePasswordCard's
                                submit button once active; off state matches
                                DashboardIdentityCard's "Change Password"
                                quick-link button (variant="outline",
                                border-strong at rest, brand tint on
                                hover). */}
                            <Button
                                size="sm"
                                variant={rowClickSelects ? "brand" : "outline"}
                                className={
                                    rowClickSelects
                                        ? undefined
                                        : "border-border-strong bg-bg-surface text-fg-muted hover:bg-brand-subtle hover:border-brand-solid hover:text-brand-fg"
                                }
                                onClick={() => setRowClickSelects((v) => !v)}
                                aria-pressed={rowClickSelects}
                            >
                                <MousePointerClick size={14} aria-hidden="true" />
                                {t("activeSessionsCard.rowClickSelect")}
                            </Button>
                        </AppTooltip>
                        <TableActionButton
                            size="sm"
                            colorPalette="red"
                            className={DESTRUCTIVE_TABLE_ACTION_CLASSNAME}
                            onClick={() => setBulkEnding(true)}
                            disabled={selectedSessionIds.size === 0}
                        >
                            <MonitorOff size={14} aria-hidden="true" />
                            {t("activeSessionsCard.logOutSelected")}
                        </TableActionButton>
                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setSelectedSessionIds(new Set())}
                            disabled={selectedSessionIds.size === 0}
                        >
                            <X size={14} aria-hidden="true" />
                            {t("ui_text:clearSelection")}
                        </Button>
                    </div>
                </div>
            )}

            <DataTable
                columns={columns}
                rows={sessions}
                rowKey={(s) => s.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage={t("activeSessionsCard.errorLoadSessions")}
                emptyMessage={t("activeSessionsCard.noActiveSessions")}
                emptyIcon={<MonitorOff size={32} aria-hidden="true" />}
                startIndex={0}
                rowClickSelects={rowClickSelects}
                selectable={!!sessions && sessions.length > 1}
                selectedKeys={selectedSessionIds}
                onSelectionChange={setSelectedSessionIds}
                disabledKeys={disabledSessionKeys}
            />

            <ConfirmDialog
                isOpen={bulkEnding}
                title={t("activeSessionsCard.bulkEndDialog.title", { count: selectedSessionIds.size })}
                description={t("activeSessionsCard.bulkEndDialog.description", { count: selectedSessionIds.size })}
                confirmLabel={t("activeSessionsCard.bulkEndDialog.confirmLabel")}
                isLoading={bulkRevokeMutation.isPending}
                onConfirm={handleBulkConfirm}
                onCancel={() => setBulkEnding(false)}
            />

            <ConfirmDialog
                isOpen={!!endingSession}
                title={dialogSession?.is_current ? t("activeSessionsCard.endDialog.logoutThisDeviceTitle") : t("activeSessionsCard.endDialog.endSessionTitle")}
                description={
                    dialogSession?.is_current
                        ? t("activeSessionsCard.endDialog.logoutThisDeviceDescription")
                        : t("activeSessionsCard.endDialog.endSessionDescription", {
                              device: parseUserAgent(dialogSession?.user_agent ?? null),
                              ipSuffix: dialogSession?.ip_address ? ` (${dialogSession.ip_address})` : "",
                          })
                }
                confirmLabel={t("activeSessionsCard.endDialog.confirmLabel")}
                isLoading={endingSession?.is_current ? logoutMutation.isPending : revokeMutation.isPending}
                onConfirm={handleConfirm}
                onCancel={() => setEndingSession(null)}
            />

            <ConfirmDialog
                isOpen={logoutAllConfirmOpen}
                title={t("logoutAllDialog.title")}
                description={t("logoutAllDialog.description")}
                confirmLabel={t("logoutAllDialog.confirmLabel")}
                isLoading={logoutAllMutation.isPending}
                onConfirm={() => {
                    logoutAllMutation.mutate();
                    setLogoutAllConfirmOpen(false);
                }}
                onCancel={() => setLogoutAllConfirmOpen(false)}
            />
        </Card>
    );
};

export default ActiveSessionsCard;
