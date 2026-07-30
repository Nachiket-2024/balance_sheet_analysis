import React from "react";
import { Box, Heading, Stack, Container, Text, Flex, EmptyState } from "@chakra-ui/react";

// Reuses the same TanStack Query cache entry that useAuthSession() (called
// once at the app root) already populates, so this page doesn't duplicate
// the GET /auth/me network call or its own loading/error state machine.
import { useCurrentUserQuery } from "../auth/current_user/useCurrentUserQuery";

import Card from "../ui/Card";
import LoadingState from "../ui/LoadingState";
import FormAlert from "../ui/FormAlert";

/**
 * DashboardPage
 * ----------------------------
 * Displays the current user's information. Reads the current user from the
 * shared useCurrentUserQuery cache instead of fetching independently, so it
 * stays in sync with the rest of the app. Session controls (logout, logout
 * all devices) live in the app shell (Navbar) and ProfilePage now, not
 * here, having them on both the dashboard card and the always-visible top
 * bar was a duplicated affordance for the same action.
 */
const DashboardPage: React.FC = () => {
    const { data: user, isLoading, isError } = useCurrentUserQuery();

    return (
        <Container maxW="md">
            <Card
                p={8}
                color="fg.default"
                textAlign="center"
            >
                <Heading as="h1" fontSize="22px" mb={6} color="brand.fg">
                    Welcome to your Dashboard
                </Heading>

                {isLoading ? (
                    <LoadingState message="Loading your details..." />
                ) : isError ? (
                    <Box mb={6}><FormAlert status="error">Unable to fetch user details</FormAlert></Box>
                ) : user ? (
                    <Stack mb={6} align="flex-start">
                        <Flex align="center" justify="flex-start">
                            <Box w="30px" textAlign="center" mr={2} color="brand.fg" aria-hidden="true">
                                👤
                            </Box>
                            <Text fontSize="17px" fontWeight="semibold">
                                {user.name}
                            </Text>
                        </Flex>

                        <Flex align="center" justify="flex-start">
                            <Box w="30px" textAlign="center" mr={2} color="fg.muted" aria-hidden="true">
                                📧
                            </Box>
                            <Text fontSize="17px" color="fg.muted">
                                {user.email}
                            </Text>
                        </Flex>

                        <Flex align="center" justify="flex-start">
                            <Box w="30px" textAlign="center" mr={2} color="fg.muted" aria-hidden="true">
                                🏷️
                            </Box>
                            <Text fontSize="17px" color="fg.muted" fontWeight="medium" textTransform="capitalize">
                                {user.role ?? ":"}
                            </Text>
                        </Flex>
                    </Stack>
                ) : (
                    <EmptyState.Root mb={6} size="sm">
                        <EmptyState.Content>
                            <EmptyState.Title>No user data available</EmptyState.Title>
                        </EmptyState.Content>
                    </EmptyState.Root>
                )}
            </Card>
        </Container>
    );
};

export default DashboardPage;
