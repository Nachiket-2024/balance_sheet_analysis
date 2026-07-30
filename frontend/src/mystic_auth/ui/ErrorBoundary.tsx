import React from "react";
import { Flex, Heading, Text, VStack, Button } from "@chakra-ui/react";
import type { StackProps } from "@chakra-ui/react";

import { reportError } from "../core/errorMonitoring";

interface ErrorBoundaryProps {
    children: React.ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
}

/**
 * Top-level React error boundary. Catches an otherwise-uncaught render/
 * lifecycle error anywhere in the tree below it and shows a recoverable
 * fallback instead of the whole app unmounting to a blank white screen.
 * Deliberately a class component: React has no hook equivalent for
 * getDerivedStateFromError/componentDidCatch.
 *
 * Does not catch errors in event handlers or async code (neither of those
 * are render errors: a rejected promise or a thrown error inside an
 * onClick handler never reaches an error boundary) so those still need
 * their own try/catch, same as before this existed. Mounted once at the
 * app root (see main.tsx), outside the router, so it also catches an error
 * thrown before routing itself gets a chance to render.
 */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { hasError: false };

    static getDerivedStateFromError(): ErrorBoundaryState {
        return { hasError: true };
    }

    componentDidCatch(error: unknown, errorInfo: React.ErrorInfo): void {
        console.error("Unhandled render error:", error, errorInfo);
        // A no-op unless VITE_SENTRY_DSN is set, see core/errorMonitoring.ts.
        reportError(error, { componentStack: errorInfo.componentStack });
    }

    render(): React.ReactNode {
        if (!this.state.hasError) {
            return this.props.children;
        }

        return (
            <Flex align="center" justify="center" h="100vh" bg="bg.canvas" px={4} textAlign="center">
                <VStack {...({ spacing: 4 } as StackProps)}>
                    <Heading color="fg.error" size="2xl">Something went wrong</Heading>

                    <Text fontSize="xl" fontWeight="medium">
                        An unexpected error occurred. Reloading the page usually fixes this.
                    </Text>

                    <Button
                        colorPalette="brand"
                        size="md"
                        fontWeight="bold"
                        // A full navigation, not client-side routing: this
                        // component's own state (and potentially the whole
                        // React tree's) is in an unknown condition after a
                        // render crash, so a fresh document load is the only
                        // reliably clean recovery.
                        onClick={() => window.location.assign("/")}
                    >
                        Reload
                    </Button>
                </VStack>
            </Flex>
        );
    }
}

export default ErrorBoundary;
