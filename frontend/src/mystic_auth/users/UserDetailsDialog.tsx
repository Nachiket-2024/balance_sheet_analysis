import React from "react";
import { Badge, Button, Dialog, HStack, Portal, Stack, Text } from "@chakra-ui/react";

import { DIALOG_BACKDROP_PROPS, DIALOG_CONTENT_PROPS } from "../ui/styles/dialogStyles";
import { SECONDARY_BUTTON_PROPS } from "../ui/styles/buttonStyles";
import { formatDateTime } from "../ui/dateFormat";
import type { AdminUserRead } from "../api/users_api";

interface UserDetailsDialogProps {
    isOpen: boolean;
    user: AdminUserRead | null;
    onClose: () => void;
}

interface DetailRowProps {
    label: string;
    children: React.ReactNode;
}

/** Label/value pair, wrapping (not truncating) the value: the entire point
 * of this dialog is showing what the table's own truncated columns cut
 * off, so nothing in it should re-truncate the same content. */
const DetailRow: React.FC<DetailRowProps> = ({ label, children }) => (
    <Stack gap={0.5}>
        <Text fontSize="13px" fontWeight="semibold" textTransform="uppercase" letterSpacing="wide" color="fg.muted">
            {label}
        </Text>
        {/* as="div", not Text's default <p>: the Status row's value is an
            HStack of badges (renders a <div>), and a <div> can't legally
            nest inside a <p> - this wrapper has to stay block-agnostic
            since every row shares it regardless of what kind of content
            it holds. */}
        <Text as="div" fontSize="15px" wordBreak="break-word">
            {children}
        </Text>
    </Stack>
);

/**
 * UserDetailsDialog
 * ----------------------------
 * Read-only "View" panel for one user's full name/email/role/status/dates -
 * everything UsersPage's own Name/Email columns truncate (see DataTable.tsx's
 * `truncate` columns) for table layout reasons. Purely a display surface, no
 * mutations of its own: role changes, policy assignment, delete/reactivate/
 * purge all stay on their own existing controls. Takes the already-fetched
 * row object directly (no separate query), since UsersPage already has the
 * full, untruncated data in hand the moment a row renders.
 */
const UserDetailsDialog: React.FC<UserDetailsDialogProps> = ({ isOpen, user, onClose }) => {
    if (!user) return null;

    return (
        <Dialog.Root open={isOpen} onOpenChange={(details) => !details.open && onClose()}>
            <Portal>
                <Dialog.Backdrop {...DIALOG_BACKDROP_PROPS} />
                <Dialog.Positioner>
                    <Dialog.Content {...DIALOG_CONTENT_PROPS}>
                        <Dialog.Header>
                            <Dialog.Title>User details</Dialog.Title>
                        </Dialog.Header>
                        <Dialog.Body>
                            <Stack gap={4}>
                                <DetailRow label="Name">{user.name}</DetailRow>
                                <DetailRow label="Email">{user.email}</DetailRow>
                                <DetailRow label="Role">
                                    <Text as="span" textTransform="capitalize" color={user.role ? undefined : "fg.muted"}>
                                        {user.role ?? "No role assigned"}
                                    </Text>
                                </DetailRow>
                                <DetailRow label="Status">
                                    <HStack gap={2} wrap="wrap">
                                        <Badge colorPalette={user.is_verified ? "green" : "yellow"} size="md">
                                            {user.is_verified ? "Verified" : "Unverified"}
                                        </Badge>
                                        {user.deleted_at ? (
                                            <Badge colorPalette="red" size="md">Deleted</Badge>
                                        ) : (
                                            !user.is_active && <Badge colorPalette="red" size="md">Inactive</Badge>
                                        )}
                                        <Badge colorPalette={user.has_password ? "gray" : "blue"} size="md">
                                            {user.has_password ? "Has password" : "OAuth only"}
                                        </Badge>
                                    </HStack>
                                </DetailRow>
                                <DetailRow label="Created">{formatDateTime(user.created_at)}</DetailRow>
                                <DetailRow label="Last updated">{formatDateTime(user.updated_at)}</DetailRow>
                                {user.deleted_at && (
                                    <DetailRow label="Deleted at">{formatDateTime(user.deleted_at)}</DetailRow>
                                )}
                            </Stack>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button onClick={onClose} {...SECONDARY_BUTTON_PROPS}>
                                Close
                            </Button>
                        </Dialog.Footer>
                        <Dialog.CloseTrigger />
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>
        </Dialog.Root>
    );
};

export default UserDetailsDialog;
