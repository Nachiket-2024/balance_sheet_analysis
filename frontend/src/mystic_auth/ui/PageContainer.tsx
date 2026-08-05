import React from "react";
import { Box, Flex, Heading, Text } from "@chakra-ui/react";

interface PageContainerProps {
    title: string;
    description?: string;
    /** Right-aligned slot next to the heading, typically a primary action
     * button or a summary/stats card. */
    actions?: React.ReactNode;
    /** Extra content rendered directly below the title/description, but
     * still inside the same left-hand column as those - so it stacks
     * beneath the title while staying in the same header row as `actions`.
     * Use this (rather than putting the same content in `children`) when
     * `actions` is tall (e.g. a stats card) and this content should sit
     * beside it - a search bar/filter row, for instance - instead of
     * being pushed below the actions block's full height. */
    headerExtra?: React.ReactNode;
    children: React.ReactNode;
}

/**
 * Consistent heading/description/action-slot layout for every admin page
 * (Users, Policies, Audit Log, Account Settings) so they share the same page-header
 * rhythm instead of each hand-rolling its own Heading + Flex.
 */
const PageContainer: React.FC<PageContainerProps> = ({ title, description, actions, headerExtra, children }) => {
    return (
        <Box maxW="container.xl" mx="auto" w="full">
            <Flex
                justify="space-between"
                align="stretch"
                direction={{ base: "column", sm: "row" }}
                gap={4}
                mb={6}
            >
                <Box flex="1" minW={0} display="flex" flexDirection="column" justifyContent="space-between">
                    <Box>
                        <Heading as="h1" size="xl" color="fg.default">
                            {title}
                        </Heading>
                        {description && (
                            <Text color="fg.muted" mt={1} fontSize="15px">
                                {description}
                            </Text>
                        )}
                    </Box>
                    {headerExtra && <Box mt={4}>{headerExtra}</Box>}
                </Box>
                {actions && <Box>{actions}</Box>}
            </Flex>
            {children}
        </Box>
    );
};

export default PageContainer;
