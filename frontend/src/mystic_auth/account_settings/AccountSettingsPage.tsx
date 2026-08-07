import React, { useState } from "react";
import { Flex, Stack } from "@chakra-ui/react";

import PageContainer from "../ui/PageContainer";
import { useAuthStore } from "../store/authStore";
import ProfileNameCard from "./ProfileNameCard";
import ChangePasswordCard from "./ChangePasswordCard";
import AccountStatusCard from "./AccountStatusCard";
import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning";

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
 *
 * Composes three independent widgets, each owning its own state/validation/
 * mutation: ProfileNameCard (name), ChangePasswordCard (password), and
 * AccountStatusCard (read-only password status + policy list). This page
 * only owns what has to live above all three: the combined unsaved-changes
 * warning, since from the user's perspective "I have unsaved changes"
 * doesn't care which card they're in.
 */
const AccountSettingsPage: React.FC = () => {
    const name = useAuthStore((s) => s.name);
    const hasPassword = useAuthStore((s) => s.hasPassword);

    const [nameDirty, setNameDirty] = useState(false);
    const [passwordDirty, setPasswordDirty] = useState(false);
    useUnsavedChangesWarning(nameDirty || passwordDirty);

    return (
        <PageContainer title="Account Settings" description="Update your name and password.">
            <Flex gap={6} align="stretch" wrap="wrap">
                <Stack gap={5} flex="1 1 320px" maxW="lg">
                    <ProfileNameCard name={name} onDirtyChange={setNameDirty} />
                    <AccountStatusCard hasPassword={hasPassword} />
                </Stack>

                <ChangePasswordCard hasPassword={hasPassword} onDirtyChange={setPasswordDirty} />
            </Flex>
        </PageContainer>
    );
};

export default AccountSettingsPage;
