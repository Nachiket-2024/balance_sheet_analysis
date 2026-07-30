import React from "react";
import { Flex, Spinner, Text } from "@chakra-ui/react";

interface LoadingStateProps {
    message: string;
    // When true, fills the viewport (h="100vh") for whole-page loading gates. When false, sizes
    // to its container, for loading states nested inside a page (e.g. a card body).
    fullScreen?: boolean;
}

/**
 * Single consistent loading treatment, replacing what used to be three near-duplicate local
 * components that had each independently drifted to a slightly different spinner color.
 */
const LoadingState: React.FC<LoadingStateProps> = ({ message, fullScreen = false }) => {
    return (
        <Flex
            align="center"
            justify="center"
            h={fullScreen ? "100vh" : "full"}
            py={fullScreen ? undefined : 12}
            bg={fullScreen ? "bg.canvas" : undefined}
        >
            <Spinner size="xl" color="brand.solid" />
            <Text ml={4} fontSize="lg" color="fg.muted">{message}</Text>
        </Flex>
    );
};

export default LoadingState;
