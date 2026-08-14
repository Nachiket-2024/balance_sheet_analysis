import React, { useEffect, useState } from "react";
import { Badge, Box, Heading, Container, Text, Separator, EmptyState, HStack, Stack, Flex } from "@chakra-ui/react";
import { useNavigate } from "react-router";
import { CalendarDays, Clock, LogOut, Mail, Monitor, Pencil, ShieldCheck, User } from "lucide-react";
import { useTranslation } from "react-i18next";

// Reuses the same TanStack Query cache entry that useAuthSession() (called
// once at the app root) already populates, so this page doesn't duplicate
// the GET /auth/me network call or its own loading/error state machine.
import { useCurrentUserQuery } from "../auth/current_user/useCurrentUserQuery";
import { useLogoutAllMutation } from "../auth/logout_all/useLogoutAllMutation";
import { useLastLoginQuery } from "./useLastLoginQuery";
import { formatMemberSince, formatTimeOnly } from "../ui/dateFormat";
import { useLanguageStore } from "../store/languageStore";
import ManageSessionsCard from "./manage_sessions/ManageSessionsCard";

import Card from "../ui/Card";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import ConfirmDialog from "../ui/ConfirmDialog";
import TableActionButton from "../ui/TableActionButton";

interface StatItemProps {
    icon: React.ReactNode;
    label: string;
    /** A plain string renders as one line; Last login passes a two-line
     * (date, then time) node instead - see below. */
    value: React.ReactNode;
}

/** One "label + value" cell in the stats row, label on top (small, muted,
 * matching a typical stat-card convention) with the actual value
 * underneath as the primary read. */
const StatItem: React.FC<StatItemProps> = ({ icon, label, value }) => (
    <Box textAlign="center" flexShrink={0}>
        <HStack gap={1} justify="center" color="fg.muted" whiteSpace="nowrap">
            {icon}
            <Text fontSize="14px" fontWeight="semibold" textTransform="uppercase" letterSpacing="wide" whiteSpace="nowrap">
                {label}
            </Text>
        </HStack>
        <Box color="fg.default" mt={1}>
            {value}
        </Box>
    </Box>
);

/**
 * DashboardPage
 * ----------------------------
 * Displays the current user's information. Reads the current user from the
 * shared useCurrentUserQuery cache instead of fetching independently, so it
 * stays in sync with the rest of the app. Session controls (logout, logout
 * all devices) live in the app shell (Navbar) and AccountSettingsPage too; the
 * Logout All quick action below is a shortcut to that same flow, not a
 * separate implementation of it.
 */
const DashboardPage: React.FC = () => {
    const { t } = useTranslation("dashboard");
    // See AllAuthorizationLogSection.tsx's matching comment: dates use
    // chromeLanguage, not pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const { data: user, isLoading, isError } = useCurrentUserQuery();
    const { data: lastLoginAt } = useLastLoginQuery();
    const navigate = useNavigate();

    const logoutAllMutation = useLogoutAllMutation();
    const [confirmOpen, setConfirmOpen] = useState(false);

    useEffect(() => {
        if (logoutAllMutation.isSuccess) navigate("/login");
    }, [logoutAllMutation.isSuccess, navigate]);

    return (
        <Container maxW="8xl">
            <Stack gap={6}>
            {/* Both cards are full-width and laid out as a horizontal row of
                sections (identity, stats, actions) rather than the previous
                narrow 340px column stacked vertically down the page - a
                short, wide banner reads faster than a tall one, and it
                matches the Manage Sessions table below it, which is
                already wide/horizontal by nature. */}
            <Card p={7} color="fg.default">
                {isLoading ? (
                    <LoadingState message={t("loadingDetails")} />
                ) : isError ? (
                    <Box><FormAlert status="error">{t("unableToFetch")}</FormAlert></Box>
                ) : user ? (
                    <Stack gap={3}>
                        {/* Natural-width blocks with a small fixed gap and a
                            vertical divider between each section, instead of
                            flex="1" + justify="space-between" stretching
                            identity+stats to fill all the way out to the
                            button column - that pushed a big, content-free
                            gap between "identity" and "stats" whenever the
                            card was wider than the two of them combined.
                            align="flex-start": name, every stat's label, and
                            the first button all start at the exact same top
                            line, regardless of which block ends up taller
                            below that line (Last login's value runs two
                            lines; the others don't). */}
                        {/* align="stretch" on the row so the bare <Separator>s
                            (no alignSelf override) stretch to match whichever
                            block is tallest - Last login's two-line value
                            usually makes that the stats block - instead of a
                            guessed fixed height that risks looking too short
                            next to it. Each actual content block overrides
                            back to alignSelf="flex-start" so name, every
                            stat's label, and the first button still all
                            start at the exact same top line regardless. */}
                        <Flex align="stretch" justify="space-between" gap={6} wrap="wrap" rowGap={4}>
                            <HStack gap={4} alignSelf="flex-start">
                                <Box
                                    display="flex"
                                    alignItems="center"
                                    justifyContent="center"
                                    boxSize="56px"
                                    flexShrink={0}
                                    borderRadius="full"
                                    bg="brand.subtle"
                                    color="brand.fg"
                                >
                                    <User size={28} aria-hidden="true" />
                                </Box>

                                <Box>
                                    <HStack gap={2} wrap="wrap">
                                        <Heading as="h1" fontSize="21px" fontWeight="semibold">
                                            {user.name}
                                        </Heading>
                                        <Badge
                                            colorPalette={user.role ? "brand" : "gray"}
                                            variant="subtle"
                                            px={2.5}
                                            py={1}
                                            fontSize="15px"
                                            borderRadius="full"
                                            textTransform="capitalize"
                                            display="inline-flex"
                                            alignItems="center"
                                            gap={1}
                                        >
                                            <ShieldCheck size={14} aria-hidden="true" />
                                            {user.role ?? t("noRole")}
                                        </Badge>
                                    </HStack>
                                    <Box display="flex" alignItems="center" gap={2} color="fg.muted" mt={1}>
                                        <Mail size={16} aria-hidden="true" />
                                        <Text fontSize="16px">{user.email}</Text>
                                    </Box>
                                </Box>
                            </HStack>

                            <Separator orientation="vertical" display={{ base: "none", md: "block" }} />

                            {/* align="flex-start": every label sits on the
                                same top line, and every value starts on
                                the same line directly beneath it - Last
                                login's value simply grows a second line
                                below that shared starting point instead
                                of (with the default center-alignment)
                                shifting its whole two-line block up so
                                neither line lines up with its siblings'
                                single line. */}
                            <HStack gap={8} align="flex-start" alignSelf="flex-start" wrap="wrap" rowGap={4}>
                                <StatItem
                                    icon={<CalendarDays size={15} aria-hidden="true" />}
                                    label={t("memberSince")}
                                    value={<Text fontSize="16px" fontWeight="semibold">{formatMemberSince(user.created_at, language)}</Text>}
                                />
                                <StatItem
                                    icon={<Clock size={15} aria-hidden="true" />}
                                    label={t("lastLogin")}
                                    value={
                                        lastLoginAt ? (
                                            // Date on one line, time on the next - the combined
                                            // "Aug 1, 2026, 4:23 PM" string is the widest thing in
                                            // this row by far, and this stat sits in a fixed-width
                                            // column next to two much shorter ones, so splitting it
                                            // keeps that column no wider than "Member since"/
                                            // "Active sessions" instead of stretching the whole row.
                                            <Box lineHeight="1.3">
                                                <Text fontSize="16px" fontWeight="semibold">{formatMemberSince(lastLoginAt, language)}</Text>
                                                <Text fontSize="15px" fontWeight="medium" color="fg.muted">{formatTimeOnly(lastLoginAt, language)}</Text>
                                            </Box>
                                        ) : (
                                            <Text fontSize="16px" fontWeight="semibold">-</Text>
                                        )
                                    }
                                />
                                <StatItem
                                    icon={<Monitor size={15} aria-hidden="true" />}
                                    label={user.active_sessions === 1 ? t("activeSession") : t("activeSessions")}
                                    value={<Text fontSize="16px" fontWeight="semibold">{user.active_sessions}</Text>}
                                />
                            </HStack>

                            <Separator orientation="vertical" display={{ base: "none", md: "block" }} />

                            <Stack gap={4} minW="140px" flexShrink={0} alignSelf="flex-start">
                                <TableActionButton
                                    size="sm"
                                    fontSize="16px"
                                    colorPalette="orange"
                                    onClick={() => navigate("/account-settings")}
                                >
                                    <Pencil size={16} aria-hidden="true" /> {t("accountSettingsButton")}
                                </TableActionButton>
                                <TableActionButton
                                    size="sm"
                                    fontSize="16px"
                                    colorPalette="red"
                                    loading={logoutAllMutation.isPending}
                                    onClick={() => setConfirmOpen(true)}
                                >
                                    <LogOut size={16} aria-hidden="true" /> {t("logoutAllButton")}
                                </TableActionButton>
                            </Stack>
                        </Flex>

                        {logoutAllMutation.isError && <FormAlert status="error">{logoutAllMutation.error.message}</FormAlert>}
                    </Stack>
                ) : (
                    <EmptyState.Root size="sm">
                        <EmptyState.Content>
                            <EmptyState.Title>{t("noUserData")}</EmptyState.Title>
                        </EmptyState.Content>
                    </EmptyState.Root>
                )}
            </Card>

            <ManageSessionsCard />
            </Stack>

            <ConfirmDialog
                isOpen={confirmOpen}
                title={t("logoutAllDialog.title")}
                description={t("logoutAllDialog.description")}
                confirmLabel={t("logoutAllDialog.confirmLabel")}
                isLoading={logoutAllMutation.isPending}
                onConfirm={() => {
                    logoutAllMutation.mutate();
                    setConfirmOpen(false);
                }}
                onCancel={() => setConfirmOpen(false)}
            />
        </Container>
    );
};

export default DashboardPage;
