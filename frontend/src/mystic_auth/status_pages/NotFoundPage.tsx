import React from "react";
import { useNavigate } from "react-router";
import { Flex, Heading, Text, VStack, Button } from "@chakra-ui/react";

import { BRAND_SOLID_HOVER_PROPS } from "../ui/styles/buttonStyles";

const NotFoundPage: React.FC = () => {
    const navigate = useNavigate();
    return (
        <Flex align="center" justify="center" h="100vh" bg="bg.canvas" px={4} textAlign="center">
            <VStack gap={4}>
                <Heading color="fg.error" size="2xl">404</Heading>

                <Text fontSize="xl" fontWeight="medium">Oops! Page Not Found</Text>

                <Button
                    colorPalette="brand"
                    size="md"
                    fontWeight="bold"
                    onClick={() => navigate("/")}
                    {...BRAND_SOLID_HOVER_PROPS}
                >
                    Go Home
                </Button>
            </VStack>
        </Flex>
    );
};

export default NotFoundPage;
