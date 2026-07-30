import React from "react";
import { Box, Flex, Heading, Text } from "@chakra-ui/react";

interface PageContainerProps {
    title: string;
    description?: string;
    /** Right-aligned slot next to the heading, typically a primary action button. */
    actions?: React.ReactNode;
    children: React.ReactNode;
}

/**
 * Consistent heading/description/action-slot layout for every admin page
 * (Users, Policies, Audit Log, Profile) so they share the same page-header
 * rhythm instead of each hand-rolling its own Heading + Flex.
 */
const PageContainer: React.FC<PageContainerProps> = ({ title, description, actions, children }) => {
    return (
        <Box maxW="container.xl" mx="auto" w="full">
            <Flex
                justify="space-between"
                align={{ base: "flex-start", sm: "center" }}
                direction={{ base: "column", sm: "row" }}
                gap={4}
                mb={6}
            >
                <Box>
                    <Heading as="h1" size="lg" color="fg.default">
                        {title}
                    </Heading>
                    {description && (
                        <Text color="fg.muted" mt={1}>
                            {description}
                        </Text>
                    )}
                </Box>
                {actions && <Box>{actions}</Box>}
            </Flex>
            {children}
        </Box>
    );
};

export default PageContainer;
