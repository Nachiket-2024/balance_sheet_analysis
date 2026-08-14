import React from "react";
import { Badge, Box, Heading, Stack, Text, Wrap } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import Card from "../ui/Card";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";
import { useMyPoliciesQuery } from "../policies/policyQueries";

interface AccountStatusCardProps {
    hasPassword: boolean;
}

/**
 * AccountStatusCard
 * ----------------------------
 * Read-only status block: whether a password is set, and the caller's own
 * effective policies (GET /authorization/users/me/policies). Both sections
 * share one card (a divider between the two, not two separate cards):
 * splitting them cost a whole extra card's worth of padding/heading
 * overhead for no real separation of concerns - the combined card is what
 * keeps this column's total height from forcing the page to scroll on a
 * normal laptop viewport.
 */
const AccountStatusCard: React.FC<AccountStatusCardProps> = ({ hasPassword }) => {
    const { t } = useTranslation("account_settings");
    const { data: myPolicies, isLoading: policiesLoading, isError: policiesError } = useMyPoliciesQuery();

    return (
        <Card p={5} flex="1">
            <Stack gap={2}>
                <Wrap gap={2} align="center">
                    {/* fontWeight to match "My permissions" below (a real
                        Heading, semibold by default) - a plain-weight Text
                        read visibly paler/weaker next to it despite being
                        the same functional role, this card's other section
                        label, since "Authentication methods" was dropped. */}
                    <Text fontWeight="semibold">{t("accountStatus.passwordLabel")}</Text>
                    {/* size="md" to match the policy badges in "My
                        permissions" below - without it this one falls
                        back to Badge's smaller default size, reading
                        noticeably smaller next to them despite being
                        the same kind of status pill. */}
                    <Badge colorPalette={hasPassword ? "brand" : "gray"} variant="subtle" size="md">
                        {hasPassword ? t("accountStatus.set") : t("accountStatus.notSet")}
                    </Badge>
                </Wrap>
                <Text color="fg.muted" fontSize="sm">
                    {hasPassword
                        ? t("accountStatus.hasPasswordDescription")
                        : t("accountStatus.noPasswordDescription")}
                </Text>
            </Stack>

            <Box borderTopWidth="1px" borderColor="border.default" my={3} />

            <Stack gap={2}>
                <Heading as="h2" size="md">
                    {t("accountStatus.myPermissions")}
                </Heading>
                {policiesLoading ? (
                    <LoadingState message={t("accountStatus.loadingPolicies")} />
                ) : policiesError ? (
                    <FormAlert status="error">{t("accountStatus.failedLoadPolicies")}</FormAlert>
                ) : myPolicies && myPolicies.policies.length > 0 ? (
                    <Wrap gap={2}>
                        {myPolicies.policies.map((p) => (
                            <Badge key={p.name} colorPalette="brand" variant="subtle" size="md" fontSize="15px">
                                {p.name}
                            </Badge>
                        ))}
                    </Wrap>
                ) : (
                    <Text color="fg.muted">{t("accountStatus.noPolicies")}</Text>
                )}
            </Stack>
        </Card>
    );
};

export default AccountStatusCard;
