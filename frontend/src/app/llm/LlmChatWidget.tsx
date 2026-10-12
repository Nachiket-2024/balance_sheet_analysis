import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Button, Card, FormAlert, Textarea } from "../sdk";
import { chatApi, submitChatFeedbackApi } from "../api/llm_api";

interface LlmChatWidgetProps {
    companyId: number;
}

interface Exchange {
    question: string;
    answer: string;
    feedback?: boolean;
}

/**
 * A grounded Q&A box scoped to one company (problem statement 1a). The
 * backend (llm_routes.py) injects that
 * company's real balance-sheet figures into the LLM prompt and re-checks
 * PBAC per request, so this widget never needs to duplicate access logic
 * client-side; it only renders whatever the backend agrees to answer.
 */
const LlmChatWidget: React.FC<LlmChatWidgetProps> = ({ companyId }) => {
    const { t } = useTranslation("llm");
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
        <Card className="p-5">
            <h2 className="mb-3 text-lg font-semibold">
                {t("widgetTitle")}
            </h2>

            {history.length > 0 && (
                <div className="mb-4 flex max-h-80 flex-col gap-3 overflow-y-auto">
                    {history.map((exchange, i) => (
                        <div key={i}>
                            <p className="font-medium">
                                {exchange.question}
                            </p>
                            <p className="mt-1 whitespace-pre-wrap text-fg-muted">
                                {exchange.answer}
                            </p>
                            <div className="mt-2 flex gap-2 text-xs"><Button size="sm" variant="outline" disabled={exchange.feedback !== undefined} onClick={() => { submitChatFeedbackApi(companyId, true); setHistory((prev) => prev.map((item, index) => index === i ? { ...item, feedback: true } : item)); }}>{t("helpful")}</Button><Button size="sm" variant="outline" disabled={exchange.feedback !== undefined} onClick={() => { submitChatFeedbackApi(companyId, false); setHistory((prev) => prev.map((item, index) => index === i ? { ...item, feedback: false } : item)); }}>{t("notHelpful")}</Button></div>
                        </div>
                    ))}
                </div>
            )}

            {mutation.isError && (
                <div className="mb-3">
                    <FormAlert status="error">{t("unableToReach")}</FormAlert>
                </div>
            )}

            <form onSubmit={handleSubmit}>
                <div className="flex flex-col gap-2">
                    <Textarea
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder={t("questionPlaceholder")}
                        rows={2}
                    />
                    <Button
                        type="submit"
                        variant="brand"
                        className="self-start"
                        loading={mutation.isPending}
                    >
                        {t("ask")}
                    </Button>
                </div>
            </form>
        </Card>
    );
};

export default LlmChatWidget;
