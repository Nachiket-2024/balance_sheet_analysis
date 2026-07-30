import React, { useState } from "react";
import { Badge, Button, Dialog, HStack, NativeSelect, Portal, Stack, Text, Wrap } from "@chakra-ui/react";

import { useUserPoliciesQuery, usePoliciesQuery } from "../policies/policyQueries";
import { useAssignPolicyMutation, useRevokePolicyMutation } from "../policies/policyMutations";
import { toaster } from "../ui/toasterInstance";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { useAuthStore } from "../store/authStore";

interface UserPoliciesDialogProps {
    isOpen: boolean;
    userEmail: string | null;
    onClose: () => void;
}

/**
 * UserPoliciesDialog
 * ----------------------------
 * Shows the policies currently assigned to one user, with controls to
 * assign an additional policy or revoke an existing one. This is the
 * frontend surface for /authorization/users/{email}/policies: the actual
 * grant/revoke decision is enforced server-side either way, this is purely
 * the admin UI for it.
 */
const UserPoliciesDialog: React.FC<UserPoliciesDialogProps> = ({ isOpen, userEmail, onClose }) => {
    const [selectedPolicy, setSelectedPolicy] = useState("");
    const currentUserEmail = useAuthStore((s) => s.email);
    // Revoking your OWN policy here has no confirmation and no
    // /auth/me refetch of its own: the Zustand permissions cache (source
    // for every IfCan/ProtectedRoute check) would stay stale until the
    // next reload, so a self-revoke could silently strand you in a UI that
    // still shows controls you no longer have access to. Simplest safe
    // fix, consistent with UsersPage's existing self-delete/self-role-edit
    // guards: block self-revoke entirely from this dialog.
    const isSelf = !!userEmail && userEmail === currentUserEmail;

    const userPoliciesQuery = useUserPoliciesQuery(userEmail ?? "", isOpen && !!userEmail);
    const allPoliciesQuery = usePoliciesQuery();
    const assignMutation = useAssignPolicyMutation();
    const revokeMutation = useRevokePolicyMutation();

    if (!userEmail) return null;

    const assignedNames = new Set((userPoliciesQuery.data?.policies ?? []).map((p) => p.name));
    const availableToAssign = (allPoliciesQuery.data ?? []).filter((p) => !assignedNames.has(p.name));

    const handleAssign = () => {
        if (!selectedPolicy) return;
        assignMutation.mutate(
            { userEmail, policyName: selectedPolicy },
            {
                onSuccess: () => {
                    toaster.create({ title: `Assigned "${selectedPolicy}"`, type: "success" });
                    setSelectedPolicy("");
                },
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const handleRevoke = (policyName: string) => {
        revokeMutation.mutate(
            { userEmail, policyName },
            {
                onSuccess: () => toaster.create({ title: `Revoked "${policyName}"`, type: "success" }),
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    return (
        <Dialog.Root open={isOpen} onOpenChange={(details) => !details.open && onClose()} size="lg">
            <Portal>
                <Dialog.Backdrop />
                <Dialog.Positioner>
                    <Dialog.Content>
                        <Dialog.Header>
                            <Dialog.Title>Policies for {userEmail}</Dialog.Title>
                        </Dialog.Header>
                        <Dialog.Body>
                            <Stack gap={4}>
                                {isSelf && (
                                    <Text fontSize="sm" color="fg.muted">
                                        You cannot revoke your own policies from here : ask another admin,
                                        or use a different account.
                                    </Text>
                                )}
                                {userPoliciesQuery.isLoading ? (
                                    <LoadingState message="Loading policies..." />
                                ) : userPoliciesQuery.isError ? (
                                    <FormAlert status="error">Failed to load this user's policies</FormAlert>
                                ) : (userPoliciesQuery.data?.policies ?? []).length === 0 ? (
                                    <Text color="fg.muted">No policies assigned yet.</Text>
                                ) : (
                                    <Wrap gap={2}>
                                        {(userPoliciesQuery.data?.policies ?? []).map((p) => (
                                            <Badge key={p.name} colorPalette="brand" variant="subtle" px={2} py={1}>
                                                <HStack gap={2}>
                                                    <Text>{p.name}</Text>
                                                    <IfCan action={PERMISSIONS.POLICIES_REVOKE}>
                                                        <Button
                                                            size="2xs"
                                                            variant="ghost"
                                                            aria-label={`Revoke ${p.name}`}
                                                            onClick={() => handleRevoke(p.name)}
                                                            disabled={isSelf}
                                                            title={isSelf ? "You cannot revoke your own policies here" : undefined}
                                                            loading={
                                                                revokeMutation.isPending &&
                                                                revokeMutation.variables?.policyName === p.name
                                                            }
                                                        >
                                                            ✕
                                                        </Button>
                                                    </IfCan>
                                                </HStack>
                                            </Badge>
                                        ))}
                                    </Wrap>
                                )}

                                <IfCan action={PERMISSIONS.POLICIES_ASSIGN}>
                                    <HStack>
                                        <NativeSelect.Root size="sm" flex={1}>
                                            <NativeSelect.Field
                                                value={selectedPolicy}
                                                onChange={(e) => setSelectedPolicy(e.target.value)}
                                                aria-label="Select a policy to assign"
                                            >
                                                <option value="">Select a policy to assign...</option>
                                                {availableToAssign.map((p) => (
                                                    <option key={p.name} value={p.name}>
                                                        {p.name}
                                                    </option>
                                                ))}
                                            </NativeSelect.Field>
                                            <NativeSelect.Indicator />
                                        </NativeSelect.Root>
                                        <Button
                                            size="sm"
                                            colorPalette="brand"
                                            onClick={handleAssign}
                                            disabled={!selectedPolicy}
                                            loading={assignMutation.isPending}
                                        >
                                            Assign
                                        </Button>
                                    </HStack>
                                </IfCan>
                            </Stack>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button variant="ghost" onClick={onClose}>
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

export default UserPoliciesDialog;
