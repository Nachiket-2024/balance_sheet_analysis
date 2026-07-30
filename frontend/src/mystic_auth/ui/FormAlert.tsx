import React from "react";
import { Alert } from "@chakra-ui/react";

interface FormAlertProps {
    // The two states auth forms need today. Chakra's Alert also supports
    // "warning"/"info"/"neutral" if a future caller needs them.
    status: "error" | "success";
    children: React.ReactNode;
}

/**
 * Thin wrapper around Chakra v3's Alert.Root, replacing the ad hoc
 * `<Text color="red.500">` / `<Text color="green.500">` pattern repeated
 * across every auth form for error/success feedback.
 */
const FormAlert: React.FC<FormAlertProps> = ({ status, children }) => {
    return (
        <Alert.Root status={status} borderRadius="md">
            <Alert.Indicator />
            <Alert.Title>{children}</Alert.Title>
        </Alert.Root>
    );
};

export default FormAlert;
