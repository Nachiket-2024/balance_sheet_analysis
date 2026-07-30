import React, { useState } from "react";
import { Badge, Button, Field, Heading, Input, Stack, Text, Wrap } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import Card from "../ui/Card";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import PasswordRulesChecklist from "../auth/password_rules/PasswordRulesChecklist";
import { useAuthStore } from "../store/authStore";
import { useMyPoliciesQuery } from "../policies/policyQueries";
import { useUpdateMyProfileMutation } from "./useUpdateMyProfileMutation";
import LogoutAllButton from "../auth/logout_all/LogoutAllButton";
import { checkPasswordRules, evaluatePasswordStrength, validatePassword } from "../auth/password_rules/passwordRules";
import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning";
import { toaster } from "../ui/toasterInstance";

/**
 * ProfilePage
 * ----------------------------
 * Self-service account page: view own profile (name/email/role, the same
 * fields DashboardPage shows) plus the effective policies currently granted
 * (GET /authorization/users/me/policies), and update own name/password
 * (PUT /users/me). No permission required beyond authentication: this is
 * exactly the self-service surface users:read_own/users:update_own exist
 * for.
 */
const ProfilePage: React.FC = () => {
    const name = useAuthStore((s) => s.name);
    const email = useAuthStore((s) => s.email);
    const role = useAuthStore((s) => s.role);
    const hasPassword = useAuthStore((s) => s.hasPassword);

    const { data: myPolicies, isLoading: policiesLoading, isError: policiesError } = useMyPoliciesQuery();

    const [editedName, setEditedName] = useState(name ?? "");
    const [newPassword, setNewPassword] = useState("");
    const [currentPassword, setCurrentPassword] = useState("");
    const [localError, setLocalError] = useState("");

    const updateMutation = useUpdateMyProfileMutation();

    const rules = checkPasswordRules(newPassword);
    const strength = evaluatePasswordStrength(newPassword);

    const isDirty = editedName !== (name ?? "") || newPassword.length > 0;
    useUnsavedChangesWarning(isDirty);

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();
        setLocalError("");

        if (newPassword) {
            const passwordError = validatePassword(newPassword);
            if (passwordError) {
                setLocalError(passwordError);
                return;
            }
            // Only an account that already has a password needs to confirm
            // it: setting one for the first time on an OAuth-only account
            // has nothing to confirm against.
            if (hasPassword && !currentPassword) {
                setLocalError("Enter your current password to set a new one");
                return;
            }
        }

        const payload: { name?: string; password?: string; current_password?: string } = {};
        if (editedName && editedName !== name) payload.name = editedName;
        if (newPassword) {
            payload.password = newPassword;
            if (hasPassword) payload.current_password = currentPassword;
        }

        if (Object.keys(payload).length === 0) {
            setLocalError("No changes to save");
            return;
        }

        updateMutation.mutate(payload, {
            onSuccess: (updated) => {
                toaster.create({ title: "Profile updated", type: "success" });
                setEditedName(updated.name);
                setNewPassword("");
                setCurrentPassword("");
            },
        });
    };

    return (
        <PageContainer title="Profile" description="View and update your account details.">
            <Stack gap={6} maxW="lg">
                <Card p={6}>
                    <Heading as="h2" size="md" mb={4}>
                        Account details
                    </Heading>
                    <Stack as="form" onSubmit={handleSubmit} gap={4}>
                        <Field.Root>
                            <Field.Label>Name</Field.Label>
                            <Input value={editedName} onChange={(e) => setEditedName(e.target.value)} />
                        </Field.Root>

                        <Field.Root>
                            <Field.Label>Email</Field.Label>
                            <Input value={email ?? ""} disabled />
                            <Field.HelperText>Email cannot be changed here.</Field.HelperText>
                        </Field.Root>

                        <Field.Root>
                            <Field.Label>Role</Field.Label>
                            <Input value={role ?? ":"} disabled textTransform="capitalize" />
                        </Field.Root>

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
                            />
                            {strength && (
                                <Text
                                    mt={1}
                                    fontSize="sm"
                                    fontWeight="bold"
                                    color={
                                        strength === "Weak" ? "red.500" : strength === "Medium" ? "orange.400" : "green.500"
                                    }
                                >
                                    Strength: {strength}
                                </Text>
                            )}
                        </Field.Root>

                        {newPassword && hasPassword && (
                            <Field.Root>
                                <Field.Label>Current password</Field.Label>
                                <Input
                                    type="password"
                                    value={currentPassword}
                                    onChange={(e) => setCurrentPassword(e.target.value)}
                                    placeholder="Required to confirm this change"
                                />
                            </Field.Root>
                        )}

                        {newPassword && <PasswordRulesChecklist rules={rules} />}

                        {localError && <FormAlert status="error">{localError}</FormAlert>}
                        {updateMutation.isError && <FormAlert status="error">{updateMutation.error.message}</FormAlert>}

                        <Button
                            type="submit"
                            colorPalette="brand"
                            alignSelf="flex-start"
                            loading={updateMutation.isPending}
                            loadingText="Saving..."
                        >
                            Save changes
                        </Button>
                    </Stack>
                </Card>

                <Card p={6}>
                    <Heading as="h2" size="md" mb={4}>
                        Authentication methods
                    </Heading>
                    <Stack gap={2}>
                        <Wrap gap={2} align="center">
                            <Text>Password</Text>
                            <Badge colorPalette={hasPassword ? "brand" : "gray"} variant="subtle">
                                {hasPassword ? "Set" : "Not set"}
                            </Badge>
                        </Wrap>
                        <Text color="fg.muted" fontSize="sm">
                            {hasPassword
                                ? "You can sign in with your email and password. If this email is also linked to a Google account, Google sign-in works too."
                                : "This account currently signs in with Google only. Set a password below to also enable email/password sign-in."}
                        </Text>
                    </Stack>
                </Card>

                <Card p={6}>
                    <Heading as="h2" size="md" mb={4}>
                        My permissions
                    </Heading>
                    {policiesLoading ? (
                        <LoadingState message="Loading your policies..." />
                    ) : policiesError ? (
                        <FormAlert status="error">Failed to load your policies</FormAlert>
                    ) : myPolicies && myPolicies.policies.length > 0 ? (
                        <Wrap gap={2}>
                            {myPolicies.policies.map((p) => (
                                <Badge key={p.name} colorPalette="brand" variant="subtle">
                                    {p.name}
                                </Badge>
                            ))}
                        </Wrap>
                    ) : (
                        <Text color="fg.muted">No policies assigned.</Text>
                    )}
                </Card>

                <Card p={6}>
                    <Heading as="h2" size="md" mb={2}>
                        Session
                    </Heading>
                    <Text color="fg.muted" mb={4}>
                        End every other active session for this account (e.g. after using a shared or lost
                        device). The Logout button in the top bar only ends this session.
                    </Text>
                    <LogoutAllButton />
                </Card>
            </Stack>
        </PageContainer>
    );
};

export default ProfilePage;
