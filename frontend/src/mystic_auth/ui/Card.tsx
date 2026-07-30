import React from "react";
import { Card as ChakraCard } from "@chakra-ui/react";
import type { CardRootProps } from "@chakra-ui/react";

/**
 * Thin wrapper around Chakra v3's Card.Root with the app's standard surface styling (theme
 * surface/border tokens, rounded corners, shadow). All CardRootProps pass through, so callers
 * can still override spacing/alignment per use.
 */
const Card: React.FC<CardRootProps> = ({ children, ...props }) => {
    return (
        <ChakraCard.Root
            bg="bg.surface"
            borderWidth="1px"
            borderColor="border.default"
            rounded="xl"
            shadow="md"
            {...props}
        >
            {children}
        </ChakraCard.Root>
    );
};

export default Card;
