import React, { useState } from "react";
import { Badge, Box, Button, Field, Flex, Heading, Input, Stack, Text, Wrap } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import Card from "../ui/Card";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import PasswordRulesChecklist from "../auth/password_rules/PasswordRulesChecklist";
import { useAuthStore } from "../store/authStore";
import { useMyPoliciesQuery } from "../policies/policyQueries";
import { useUpdateMyAccountMutation } from "./useUpdateMyAccountMutation";
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../auth/password_rules/passwordRules";
import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning";
import { toaster } from "../ui/toaster/toasterInstance";
import { BRAND_SOLID_HOVER_PROPS } from "../ui/styles/buttonStyles";
import { SEARCH_INPUT_PROPS } from "../ui/styles/inputStyles";

/**
 * AccountSettingsPage (nav label/route: "Account Settings")
 * ----------------------------
 * Self-service account management: rename your own account, change/set your
 * password, and see your own effective policies (GET /authorization/users/
 * me/policies) - name and/or password both PUT /users/me, via two
 * independent forms/cards, see below. Deliberately doesn't repeat email/role/
 * member-since/session-count: DashboardPage already shows those as read-only
 * context, so this page only holds what's actually actionable here. No
 * permission required beyond authentication: this is exactly the
 * self-service surface users:read_own/users:update_own exist for.
 */
const AccountSettingsPage: React.FC = () => {
    const name = useAuthStore((s) => s.name);
    const hasPassword = useAuthStore((s) => s.hasPassword);

    const { data: myPolicies, isLoading: policiesLoading, isError: policiesError } = useMyPoliciesQuery();

    const [editedName, setEditedName] = useState(name ?? "");
    const [nameError, setNameError] = useState("");

    const [newPassword, setNewPassword] = useState("");
    const [currentPassword, setCurrentPassword] = useState("");
    const [passwordError, setPasswordError] = useState("");

    // Two independent mutation instances (not one shared), so each card's
    // own pending/error state stays scoped to itself - saving a name change
    // must never show a loading spinner or a stale error on the unrelated
    // password card, and vice versa.
    const nameMutation = useUpdateMyAccountMutation();
    const passwordMutation = useUpdateMyAccountMutation();

    const rules = checkPasswordRules(newPassword);
    const strength = evaluatePasswordStrength(newPassword);

    // Still one combined warning: from the user's perspective "I have
    // unsaved changes" doesn't care which of the two cards they're in.
    const isDirty = editedName !== (name ?? "") || newPassword.length > 0;
    useUnsavedChangesWarning(isDirty);

    const handleNameSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        setNameError("");

        if (!editedName || editedName === name) {
            setNameError("No changes to save");
            return;
        }

        nameMutation.mutate(
            { name: editedName },
            {
                onSuccess: (updated) => {
                    toaster.create({ title: "Profile updated", type: "success" });
                    setEditedName(updated.name);
                },
            }
        );
    };

    const handlePasswordSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        setPasswordError("");

        const validationError = validatePassword(newPassword);
        if (validationError) {
            setPasswordError(validationError);
            return;
        }
        // Only an account that already has a password needs to confirm it:
        // setting one for the first time on an OAuth-only account has
        // nothing to confirm against.
        if (hasPassword && !currentPassword) {
            setPasswordError("Enter your current password to set a new one");
            return;
        }

        const payload: { password: string; current_password?: string } = { password: newPassword };
        if (hasPassword) payload.current_password = currentPassword;

        passwordMutation.mutate(payload, {
            onSuccess: () => {
                toaster.create({ title: "Password updated", type: "success" });
                setNewPassword("");
                setCurrentPassword("");
            },
        });
    };

    return (
        <PageContainer title="Account Settings" description="Update your name and password.">
            <Flex gap={6} align="stretch" wrap="wrap">
                <Stack gap={5} flex="1 1 320px" maxW="lg">
                    <Card p={5}>
                        <Stack as="form" onSubmit={handleNameSubmit} gap={4}>
                            <Field.Root>
                                <Field.Label>Name</Field.Label>
                                <Input
                                    value={editedName}
                                    onChange={(e) => setEditedName(e.target.value)}
                                    aria-invalid={!!nameError || nameMutation.isError}
                                    aria-describedby={nameError ? "name-local-error" : nameMutation.isError ? "name-mutation-error" : undefined}
                                    {...SEARCH_INPUT_PROPS}
                                />
                            </Field.Root>

                            {nameError && <FormAlert status="error" id="name-local-error">{nameError}</FormAlert>}
                            {nameMutation.isError && <FormAlert status="error" id="name-mutation-error">{nameMutation.error.message}</FormAlert>}

                            <Button
                                type="submit"
                                colorPalette="brand"
                                alignSelf="flex-start"
                                loading={nameMutation.isPending}
                                loadingText="Saving..."
                                {...BRAND_SOLID_HOVER_PROPS}
                            >
                                Save changes
                            </Button>
                        </Stack>
                    </Card>

                    {/* Authentication methods + My permissions share one card
                        (a divider between the two sections, not two separate
                        cards): both are small, read-only status blocks, and
                        splitting them cost a whole extra card's worth of
                        padding/heading overhead for no real separation of
                        concerns - the combined card is what keeps this
                        column's total height from forcing the page to
                        scroll on a normal laptop viewport. */}
                    <Card p={5} flex="1">
                        <Stack gap={2}>
                            <Wrap gap={2} align="center">
                                {/* fontWeight to match "My permissions" below (a real
                                    Heading, semibold by default) - a plain-weight Text
                                    read visibly paler/weaker next to it despite being
                                    the same functional role, this card's other section
                                    label, since "Authentication methods" was dropped. */}
                                <Text fontWeight="semibold">Password</Text>
                                {/* size="md" to match the policy badges in "My
                                    permissions" below - without it this one falls
                                    back to Badge's smaller default size, reading
                                    noticeably smaller next to them despite being
                                    the same kind of status pill. */}
                                <Badge colorPalette={hasPassword ? "brand" : "gray"} variant="subtle" size="md">
                                    {hasPassword ? "Set" : "Not set"}
                                </Badge>
                            </Wrap>
                            <Text color="fg.muted" fontSize="sm">
                                {hasPassword
                                    ? "You can sign in with your email and password. If this email is also linked to a Google account, Google sign-in works too."
                                    : "This account currently signs in with Google only. Use the Change Password card to also enable email/password sign-in."}
                            </Text>
                        </Stack>

                        <Box borderTopWidth="1px" borderColor="border.default" my={3} />

                        <Stack gap={2}>
                            <Heading as="h2" size="md">
                                My permissions
                            </Heading>
                            {policiesLoading ? (
                                <LoadingState message="Loading your policies..." />
                            ) : policiesError ? (
                                <FormAlert status="error">Failed to load your policies</FormAlert>
                            ) : myPolicies && myPolicies.policies.length > 0 ? (
                                <Wrap gap={2}>
                                    {myPolicies.policies.map((p) => (
                                        <Badge key={p.name} colorPalette="brand" variant="subtle" size="md" fontSize="14px">
                                            {p.name}
                                        </Badge>
                                    ))}
                                </Wrap>
                            ) : (
                                <Text color="fg.muted">No policies assigned.</Text>
                            )}
                        </Stack>
                    </Card>
                </Stack>

                <Card p={5} flex="1 1 320px" maxW="lg">
                    <Heading as="h2" size="md" mb={3}>
                        {hasPassword ? "Change password" : "Set a password"}
                    </Heading>
                    <Stack as="form" onSubmit={handlePasswordSubmit} gap={4}>
                        <Field.Root>
                            <Field.Label>{hasPassword ? "New password" : "Set a password"}</Field.Label>
                            <Input
                                type="password"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                placeholder={
                                    hasPassword
                                        ? "Leave blank to keep your current password"
                                        : "Add a password so you can also sign in without Google"
                                }
                                aria-invalid={!!passwordError || passwordMutation.isError}
                                aria-describedby={passwordError ? "password-local-error" : passwordMutation.isError ? "password-mutation-error" : undefined}
                                {...SEARCH_INPUT_PROPS}
                            />
                            {/* Always rendered (a neutral "-" before typing starts),
                                same reasoning as SignupForm/PasswordResetConfirmForm:
                                reserving this line's height from the first render
                                means it filling in never shifts the fields below it. */}
                            <Text
                                mt={1}
                                fontSize="sm"
                                fontWeight="bold"
                                color={
                                    strength === "Weak" ? "red.500" :
                                    strength === "Medium" ? "orange.400" :
                                    strength === "Strong" ? "green.500" : "fg.muted"
                                }
                            >
                                Strength: {strength || "-"}
                            </Text>
                        </Field.Root>

                        {/* Directly below New password, not after Current
                            password: these rules describe the new password
                            you're typing above, not the confirmation field
                            below, so they read more naturally attached to
                            the field they're actually validating. */}
                        <PasswordRulesChecklist rules={rules} />

                        {/* Always rendered when the account has a password to
                            confirm against, not only once newPassword has a
                            value: this whole card should look the same the
                            moment it opens as it does mid-edit, not visibly grow
                            a field the instant you start typing. */}
                        {hasPassword && (
                            <Field.Root>
                                <Field.Label>Current password</Field.Label>
                                <Input
                                    type="password"
                                    value={currentPassword}
                                    onChange={(e) => setCurrentPassword(e.target.value)}
                                    placeholder="Required to confirm this change"
                                    aria-invalid={!!passwordError}
                                    aria-describedby={passwordError ? "password-local-error" : undefined}
                                    {...SEARCH_INPUT_PROPS}
                                />
                            </Field.Root>
                        )}

                        {passwordError && <FormAlert status="error" id="password-local-error">{passwordError}</FormAlert>}
                        {passwordMutation.isError && <FormAlert status="error" id="password-mutation-error">{passwordMutation.error.message}</FormAlert>}

                        <Button
                            type="submit"
                            colorPalette="brand"
                            alignSelf="flex-start"
                            loading={passwordMutation.isPending}
                            loadingText="Saving..."
                            {...BRAND_SOLID_HOVER_PROPS}
                        >
                            {hasPassword ? "Update password" : "Set password"}
                        </Button>
                    </Stack>
                </Card>
            </Flex>
        </PageContainer>
    );
};

export default AccountSettingsPage;
