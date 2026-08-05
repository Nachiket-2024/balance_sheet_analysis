import React from "react";
import { Alert } from "@chakra-ui/react";

interface FormAlertProps {
    // The two states auth forms need today. Chakra's Alert also supports
    // "warning"/"info"/"neutral" if a future caller needs them.
    status: "error" | "success";
    // Lets a caller point a field's aria-describedby at this alert, so a
    // screen reader announces the error in context with the input it
    // concerns, not just as an unrelated block of text elsewhere on the page.
    id?: string;
    children: React.ReactNode;
}

/**
 * Thin wrapper around Chakra v3's Alert.Root, replacing the ad hoc
 * `<Text color="red.500">` / `<Text color="green.500">` pattern repeated
 * across every auth form for error/success feedback. Chakra's Alert.Root
 * renders no `role` itself, so without one a screen reader never
 * announces this content when it appears, since it's just ordinary text
 * as far as assistive tech is concerned.
 */
const FormAlert: React.FC<FormAlertProps> = ({ status, id, children }) => {
    return (
        <Alert.Root status={status} borderRadius="md" id={id} role="alert">
            <Alert.Indicator />
            <Alert.Title>{children}</Alert.Title>
        </Alert.Root>
    );
};

export default FormAlert;
