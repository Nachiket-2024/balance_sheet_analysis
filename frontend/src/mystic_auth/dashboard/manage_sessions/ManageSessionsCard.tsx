import React, { useEffect, useState } from "react";
import { Badge, Heading, HStack, Text } from "@chakra-ui/react";
import type { CardRootProps } from "@chakra-ui/react";
import { useNavigate } from "react-router";

import Card from "../../ui/Card";
import DataTable, { type DataTableColumn } from "../../ui/DataTable";
import TableActionButton from "../../ui/TableActionButton";
import ConfirmDialog from "../../ui/ConfirmDialog";
import { toaster } from "../../ui/toaster/toasterInstance";
import { useLogoutMutation } from "../../auth/logout/useLogoutMutation";
import { formatDateTime } from "../../ui/dateFormat";
import { parseUserAgent } from "./parseUserAgent";
import { useSessionsQuery } from "./useSessionsQuery";
import { useRevokeSessionMutation } from "./useRevokeSessionMutation";
import type { SessionRead } from "../../api/auth_api";

/**
 * ManageSessionsCard
 * ----------------------------
 * Lists the caller's own active login sessions (GET /auth/sessions) as a
 * table (device/browser, IP, first-signed-in, last-seen, an action column),
 * same shape as every other admin list in the app, since this list can grow
 * just like those do. Every row gets its own working "Log out", including
 * the current device's row ("This device" badge): that one goes through the
 * ordinary single-device logout (POST /auth/logout, same as the navbar's
 * Logout button) rather than DELETE /auth/sessions/{id} - the backend
 * rejects revoking your own current session that way (it would invalidate
 * the very request doing it), so the current row's button intentionally
 * takes the other, already-safe path instead of just being disabled.
 *
 * Lives in its own `manage_sessions/` feature folder (mirroring the
 * backend's `auth/manage_sessions/` + `user_session/`), not under
 * `dashboard/`: this is session-management domain logic that happens to be
 * rendered on the Dashboard page, not something owned by the dashboard
 * feature itself.
 */
const ManageSessionsCard: React.FC<CardRootProps> = ({ ...cardProps }) => {
    const { data: sessions, isLoading, isError } = useSessionsQuery();
    const [endingSession, setEndingSession] = useState<SessionRead | null>(null);
    const revokeMutation = useRevokeSessionMutation();
    const logoutMutation = useLogoutMutation();
    const navigate = useNavigate();

    useEffect(() => {
        if (logoutMutation.isSuccess) navigate("/login");
    }, [logoutMutation.isSuccess, navigate]);

    const handleConfirm = () => {
        if (!endingSession) return;

        if (endingSession.is_current) {
            logoutMutation.mutate();
            setEndingSession(null);
            return;
        }

        revokeMutation.mutate(endingSession.id, {
            onSuccess: () => {
                toaster.create({ title: "Session ended", type: "success" });
                setEndingSession(null);
            },
            onError: (error) => {
                toaster.create({ title: error.message, type: "error" });
                setEndingSession(null);
            },
        });
    };

    const columns: DataTableColumn<SessionRead>[] = [
        {
            key: "device",
            header: "Device",
            width: "220px",
            render: (s) => {
                const label = parseUserAgent(s.user_agent);
                return (
                    <HStack gap={2} overflow="hidden">
                        <Text fontWeight="medium" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap" title={label}>
                            {label}
                        </Text>
                        {s.is_current && (
                            <Badge colorPalette="brand" variant="subtle" flexShrink={0} size="md">
                                This device
                            </Badge>
                        )}
                    </HStack>
                );
            },
        },
        { key: "ip_address", header: "IP", width: "140px", truncate: true, render: (s) => s.ip_address ?? "Unknown" },
        {
            key: "created_at",
            header: "Signed in",
            width: "190px",
            truncate: true,
            // Matches the 14px used for the date stats in the Welcome card
            // right above this table - the table's own default cell text
            // read noticeably smaller sitting directly under those.
            render: (s) => <Text fontSize="14px">{formatDateTime(s.created_at)}</Text>,
        },
        {
            key: "last_used_at",
            header: "Last seen",
            width: "190px",
            truncate: true,
            render: (s) => <Text fontSize="14px">{formatDateTime(s.last_used_at)}</Text>,
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            width: "110px",
            render: (s) => (
                <TableActionButton
                    colorPalette="red"
                    onClick={() => setEndingSession(s)}
                    loading={
                        (s.is_current && logoutMutation.isPending) ||
                        (!s.is_current && revokeMutation.isPending && revokeMutation.variables === s.id)
                    }
                >
                    Log out
                </TableActionButton>
            ),
        },
    ];

    return (
        <Card p={6} {...cardProps}>
            <Heading as="h2" size="md" mb={4}>
                Manage Sessions
            </Heading>

            <DataTable
                columns={columns}
                rows={sessions}
                rowKey={(s) => s.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage="Failed to load your sessions"
                emptyMessage="No active sessions."
                startIndex={0}
            />

            <ConfirmDialog
                isOpen={!!endingSession}
                title={endingSession?.is_current ? "Log out this device" : "End session"}
                description={
                    endingSession?.is_current
                        ? "This will log you out of this device now. Continue?"
                        : `End the session on "${parseUserAgent(endingSession?.user_agent ?? null)}"${
                              endingSession?.ip_address ? ` (${endingSession.ip_address})` : ""
                          }? That device will be signed out immediately.`
                }
                confirmLabel="Log out"
                isLoading={endingSession?.is_current ? logoutMutation.isPending : revokeMutation.isPending}
                onConfirm={handleConfirm}
                onCancel={() => setEndingSession(null)}
            />
        </Card>
    );
};

export default ManageSessionsCard;
