import React from "react";
import { Button, Text, Stack } from "@chakra-ui/react";

interface LogoutAllButtonComponentProps {
    loading: boolean;
    error: string | null;
    successMessage: string | null;
    onLogoutAll: () => void;
}

const LogoutAllButtonComponent: React.FC<LogoutAllButtonComponentProps> = ({
    loading,
    error,
    successMessage,
    onLogoutAll,
}) => {
    return (
        <Stack align="center">
            <Button
                onClick={onLogoutAll}
                loading={loading}
                loadingText="Logging out all..."
                bg="red.600"
                _hover={{ bg: "red.700" }}
                color="white"
                size="lg"
                w="160px"
                h="40px"
            >
                Logout All Devices
            </Button>

            {error && (
                <Text color="red.500" fontSize="md">
                    {error}
                </Text>
            )}

            {successMessage && (
                <Text color="green.500" fontSize="md">
                    {successMessage}
                </Text>
            )}
        </Stack>
    );
};

export default LogoutAllButtonComponent;
