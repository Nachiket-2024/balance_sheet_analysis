import React from "react";
import { Button, Text, Stack } from "@chakra-ui/react";

interface LogoutButtonComponentProps {
    loading: boolean;
    error: string | null;
    successMessage: string | null;
    onLogout: () => void;
}

const LogoutButtonComponent: React.FC<LogoutButtonComponentProps> = ({
    loading,
    error,
    successMessage,
    onLogout,
}) => {
    return (
        <Stack align="center">
            <Button
                onClick={onLogout}
                loading={loading}
                loadingText="Logging out..."
                bg="red.600"
                _hover={{ bg: "red.700" }}
                color="white"
                size="lg"
                w="160px"
                h="40px"
            >
                Logout
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

export default LogoutButtonComponent;
