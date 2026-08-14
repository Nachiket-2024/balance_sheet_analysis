import React from "react";
import { Box, Stack, Text } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import type { PasswordRules } from "./passwordRules";

interface PasswordRulesChecklistProps {
    rules: PasswordRules;
    fontSize?: string;
}

/**
 * Shared pass/fail checklist for SignupForm and PasswordResetConfirmForm.
 * Wrapped in aria-live="polite" so screen-reader users hear each rule's
 * status update as they type, instead of relying on the red/green ✓/✗ text
 * alone.
 */
const PasswordRulesChecklist: React.FC<PasswordRulesChecklistProps> = ({ rules, fontSize = "15px" }) => {
    const { t } = useTranslation("auth");

    return (
        <Box
            fontSize={fontSize}
            color="fg.muted"
            textAlign="center"
            display="flex"
            flexDirection="column"
            alignItems="center"
            aria-live="polite"
        >
            <Stack direction="row">
                <Text color={rules.lengthRule ? "fg.success" : "fg.error"} mr={6}>
                    • {rules.lengthRule ? "✓" : "✗"} {t("passwordRules.minLength")}
                </Text>
                <Text color={rules.upperRule ? "fg.success" : "fg.error"}>
                    • {rules.upperRule ? "✓" : "✗"} {t("passwordRules.upper")}
                </Text>
            </Stack>
            <Stack direction="row">
                <Text color={rules.lowerRule ? "fg.success" : "fg.error"} mr={6}>
                    • {rules.lowerRule ? "✓" : "✗"} {t("passwordRules.lower")}
                </Text>
                <Text color={rules.numberRule ? "fg.success" : "fg.error"}>
                    • {rules.numberRule ? "✓" : "✗"} {t("passwordRules.number")}
                </Text>
            </Stack>
        </Box>
    );
};

export default PasswordRulesChecklist;
