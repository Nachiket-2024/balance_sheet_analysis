import React, { useState } from "react";
import { Badge, Box, Button, Dialog, HStack, Portal, Stack, Text, Wrap } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { useUserPoliciesQuery, usePoliciesQuery } from "../policies/policyQueries";
import { useAssignPolicyMutation, useRevokePolicyMutation } from "../policies/policyMutations";
import { toaster } from "../ui/toaster/toasterInstance";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import ConfirmDialog from "../ui/ConfirmDialog";
import StyledSelect from "../ui/StyledSelect";
import { IfCan } from "../authorization/IfCan";
import { PERMISSIONS } from "../authorization/permissions";
import { useAuthStore } from "../store/authStore";
import { DIALOG_BACKDROP_PROPS, DIALOG_CONTENT_PROPS } from "../ui/styles/dialogStyles";
import { BRAND_SOLID_HOVER_PROPS, SECONDARY_BUTTON_PROPS } from "../ui/styles/buttonStyles";

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
 * the management UI for it.
 */
const UserPoliciesDialog: React.FC<UserPoliciesDialogProps> = ({ isOpen, userEmail, onClose }) => {
    const { t } = useTranslation(["users", "ui_text"]);
    const [selectedPolicy, setSelectedPolicy] = useState("");
    const [revokingPolicy, setRevokingPolicy] = useState<string | null>(null);

    // Reset on every open (same "adjust during render" pattern as
    // PolicyFormDialog.tsx, not an effect, to avoid an extra render).
    // Without this, closing the dialog mid-flow - e.g. clicking a policy
    // into `selectedPolicy` then dismissing via backdrop/Escape without
    // clicking Assign, or clicking "Revoke" on one user then dismissing
    // without confirming - leaves that state behind. Reopening for a
    // DIFFERENT user then either pre-selects a stale policy in the Assign
    // dropdown, or immediately pops the revoke ConfirmDialog describing
    // the wrong user with no click needed to summon it.
    const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
    if (isOpen !== prevIsOpen) {
        setPrevIsOpen(isOpen);
        if (isOpen) {
            setSelectedPolicy("");
            setRevokingPolicy(null);
        }
    }

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
    // usePoliciesQuery has no enabled guard of its own, and this dialog stays
    // mounted (just hidden) the whole time UsersPage is open - without gating
    // it here, every visit to /users fetched the full policies list even if
    // this dialog was never opened for any user.
    const allPoliciesQuery = usePoliciesQuery(isOpen);
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
                    toaster.create({ title: t("users:policiesDialog.assignedToast", { policyName: selectedPolicy }), type: "success" });
                    setSelectedPolicy("");
                },
                onError: (error) => toaster.create({ title: error.message, type: "error" }),
            }
        );
    };

    const handleRevokeConfirm = () => {
        if (!revokingPolicy) return;
        const policyName = revokingPolicy;
        revokeMutation.mutate(
            { userEmail, policyName },
            {
                onSuccess: () => {
                    toaster.create({ title: t("users:policiesDialog.revokedToast", { policyName }), type: "success" });
                    setRevokingPolicy(null);
                },
                onError: (error) => {
                    toaster.create({ title: error.message, type: "error" });
                    setRevokingPolicy(null);
                },
            }
        );
    };

    return (
        <Dialog.Root
            open={isOpen}
            onOpenChange={(details) => !details.open && onClose()}
            size="lg"
            closeOnInteractOutside
        >
            <Portal>
                <Dialog.Backdrop {...DIALOG_BACKDROP_PROPS} />
                <Dialog.Positioner>
                    <Dialog.Content {...DIALOG_CONTENT_PROPS}>
                        <Dialog.Header>
                            <Dialog.Title>{t("users:policiesDialog.titleFor", { email: userEmail })}</Dialog.Title>
                        </Dialog.Header>
                        <Dialog.Body>
                            <Stack gap={4}>
                                {isSelf && (
                                    <Text fontSize="sm" color="fg.muted">
                                        {t("users:policiesDialog.cannotRevokeOwn")}
                                    </Text>
                                )}
                                {userPoliciesQuery.isLoading ? (
                                    <LoadingState message={t("users:policiesDialog.loadingPolicies")} />
                                ) : userPoliciesQuery.isError ? (
                                    <FormAlert status="error">{t("users:policiesDialog.failedToLoad")}</FormAlert>
                                ) : (userPoliciesQuery.data?.policies ?? []).length === 0 ? (
                                    <Text color="fg.muted">{t("users:policiesDialog.noPoliciesAssigned")}</Text>
                                ) : (
                                    <Wrap gap={2}>
                                        {(userPoliciesQuery.data?.policies ?? []).map((p) => (
                                            <Badge key={p.name} colorPalette="brand" variant="subtle" size="md" px={2} py={1}>
                                                <HStack gap={2}>
                                                    <Text>{p.name}</Text>
                                                    <IfCan action={PERMISSIONS.POLICIES_REVOKE}>
                                                        <Button
                                                            size="2xs"
                                                            variant="ghost"
                                                            aria-label={t("users:policiesDialog.revokeAriaLabel", { policyName: p.name })}
                                                            onClick={() => setRevokingPolicy(p.name)}
                                                            disabled={isSelf}
                                                            title={isSelf ? t("users:policiesDialog.cannotRevokeOwnTitle") : undefined}
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
                                        <Box flex="1">
                                            <StyledSelect
                                                w="full"
                                                value={selectedPolicy}
                                                onChange={setSelectedPolicy}
                                                ariaLabel={t("users:policiesDialog.selectPolicyAriaLabel")}
                                                options={[
                                                    { value: "", label: t("users:policiesDialog.selectPolicyToAssign") },
                                                    ...availableToAssign.map((p) => ({ value: p.name, label: p.name })),
                                                ]}
                                            />
                                        </Box>
                                        <Button
                                            size="sm"
                                            colorPalette="brand"
                                            onClick={handleAssign}
                                            disabled={!selectedPolicy}
                                            loading={assignMutation.isPending}
                                            {...BRAND_SOLID_HOVER_PROPS}
                                        >
                                            {t("users:policiesDialog.assign")}
                                        </Button>
                                    </HStack>
                                </IfCan>
                            </Stack>
                        </Dialog.Body>
                        <Dialog.Footer>
                            <Button onClick={onClose} {...SECONDARY_BUTTON_PROPS}>
                                {t("ui_text:close")}
                            </Button>
                        </Dialog.Footer>
                        <Dialog.CloseTrigger />
                    </Dialog.Content>
                </Dialog.Positioner>
            </Portal>

            {/* Revoking strips access immediately and irreversibly (the user
                just loses whatever that policy granted, no undo) - every
                other destructive action in the app (delete/purge a user,
                delete a policy) already goes through ConfirmDialog, this
                one-click "✕" button was the odd one out. */}
            <ConfirmDialog
                isOpen={!!revokingPolicy}
                title={t("users:policiesDialog.revokeDialogTitle")}
                description={t("users:policiesDialog.revokeDialogDescription", { policyName: revokingPolicy, email: userEmail })}
                confirmLabel={t("users:policiesDialog.revokeConfirmLabel")}
                isLoading={revokeMutation.isPending}
                onConfirm={handleRevokeConfirm}
                onCancel={() => setRevokingPolicy(null)}
            />
        </Dialog.Root>
    );
};

export default UserPoliciesDialog;
