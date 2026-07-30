import React, { useState } from "react";
import { Box, Button, Stack, Text, Textarea } from "@chakra-ui/react";
import { useMutation } from "@tanstack/react-query";

import { Card, FormAlert } from "../sdk";
import { chatApi } from "../api/llm_api";

interface LlmChatWidgetProps {
    companyId: number;
}

interface Exchange {
    question: string;
    answer: string;
}

/**
 * "ChatGPT for balance-sheet analysts" (problem statement 1a): a grounded
 * Q&A box scoped to one company. The backend (llm_routes.py) injects that
 * company's real balance-sheet figures into the LLM prompt and re-checks
 * PBAC per request, so this widget never needs to duplicate access logic
 * client-side; it only renders whatever the backend agrees to answer.
 */
const LlmChatWidget: React.FC<LlmChatWidgetProps> = ({ companyId }) => {
    const [question, setQuestion] = useState("");
    const [history, setHistory] = useState<Exchange[]>([]);

    const mutation = useMutation({
        mutationFn: (q: string) => chatApi({ company_id: companyId, question: q }),
        onSuccess: (response, q) => {
            setHistory((prev) => [...prev, { question: q, answer: response.data.answer }]);
            setQuestion("");
        },
    });

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!question.trim() || mutation.isPending) return;
        mutation.mutate(question.trim());
    };

    return (
        <Card p={5}>
            <Text fontWeight="semibold" mb={3}>
                Ask about this company's performance
            </Text>

            {history.length > 0 && (
                <Stack gap={3} mb={4} maxH="320px" overflowY="auto">
                    {history.map((exchange, i) => (
                        <Box key={i}>
                            <Text fontWeight="medium" color="fg.default">
                                {exchange.question}
                            </Text>
                            <Text color="fg.muted" mt={1} whiteSpace="pre-wrap">
                                {exchange.answer}
                            </Text>
                        </Box>
                    ))}
                </Stack>
            )}

            {mutation.isError && (
                <Box mb={3}>
                    <FormAlert status="error">Unable to reach the LLM, please try again.</FormAlert>
                </Box>
            )}

            <form onSubmit={handleSubmit}>
                <Stack gap={2}>
                    <Textarea
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder="e.g. How has total debt changed over the last few years?"
                        rows={2}
                    />
                    <Button type="submit" colorPalette="brand" alignSelf="flex-end" loading={mutation.isPending}>
                        Ask
                    </Button>
                </Stack>
            </form>
        </Card>
    );
};

export default LlmChatWidget;
