import React from "react";
import { Button, Text, Stack } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { DESTRUCTIVE_SOLID_HOVER_PROPS } from "../../ui/styles/buttonStyles";

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
    const { t } = useTranslation("auth");

    return (
        <Stack align="center">
            <Button
                onClick={onLogout}
                loading={loading}
                loadingText={t("logout.loggingOut")}
                bg="red.600"
                {...DESTRUCTIVE_SOLID_HOVER_PROPS}
                color="white"
                size="lg"
                w="160px"
                h="40px"
            >
                {t("logout.logoutButton")}
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
