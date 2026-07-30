import React from "react";
import { Box, Stack, Text } from "@chakra-ui/react";

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
const PasswordRulesChecklist: React.FC<PasswordRulesChecklistProps> = ({ rules, fontSize = "15px" }) => (
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
            <Text color={rules.lengthRule ? "green.500" : "red.500"} mr={6}>
                • {rules.lengthRule ? "✓" : "✗"} At least 8 characters
            </Text>
            <Text color={rules.upperRule ? "green.500" : "red.500"}>
                • {rules.upperRule ? "✓" : "✗"} At least one uppercase letter
            </Text>
        </Stack>
        <Stack direction="row">
            <Text color={rules.lowerRule ? "green.500" : "red.500"} mr={6}>
                • {rules.lowerRule ? "✓" : "✗"} At least one lowercase letter
            </Text>
            <Text color={rules.numberRule ? "green.500" : "red.500"}>
                • {rules.numberRule ? "✓" : "✗"} At least one number
            </Text>
        </Stack>
    </Box>
);

export default PasswordRulesChecklist;
