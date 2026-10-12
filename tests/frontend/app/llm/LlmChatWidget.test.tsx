import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LlmChatWidget from "@app/llm/LlmChatWidget";
import { chatApi, submitChatFeedbackApi } from "@app/api/llm_api";

vi.mock("@app/api/llm_api", () => ({ chatApi: vi.fn(), submitChatFeedbackApi: vi.fn() }));

function renderWidget() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <ChakraProvider value={defaultSystem}>
                <LlmChatWidget companyId={7} />
            </ChakraProvider>
        </QueryClientProvider>,
    );
}

describe("LlmChatWidget", () => {
    it("submits a trimmed question and renders the grounded answer", async () => {
        vi.mocked(chatApi).mockResolvedValue({ data: { answer: "Assets increased." } } as never);
        const user = userEvent.setup();
        renderWidget();

        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "  How is cash changing?  ");
        await user.click(screen.getByRole("button", { name: "Ask" }));

        await waitFor(() => expect(screen.getByText("Assets increased.")).toBeInTheDocument());
        expect(chatApi).toHaveBeenCalledWith({ company_id: 7, question: "How is cash changing?" });
    });

    it("does not submit blank questions", async () => {
        const user = userEvent.setup();
        renderWidget();

        await user.click(screen.getByRole("button", { name: "Ask" }));

        expect(chatApi).not.toHaveBeenCalled();
    });

    it("shows a provider error", async () => {
        vi.mocked(chatApi).mockRejectedValue(new Error("provider unavailable"));
        const user = userEvent.setup();
        renderWidget();

        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "What changed?");
        await user.click(screen.getByRole("button", { name: "Ask" }));

        await waitFor(() => expect(screen.getByText("Unable to reach the LLM, please try again.")).toBeInTheDocument());
    });

    it("records helpful feedback and disables feedback actions for that answer", async () => {
        vi.mocked(chatApi)
            .mockResolvedValueOnce({ data: { answer: "Assets increased." } } as never)
            .mockResolvedValueOnce({ data: { answer: "Cash was stable." } } as never);
        vi.mocked(submitChatFeedbackApi).mockResolvedValue({} as never);
        const user = userEvent.setup();
        renderWidget();

        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "What changed?");
        await user.click(screen.getByRole("button", { name: "Ask" }));
        await waitFor(() => expect(screen.getByText("Assets increased.")).toBeInTheDocument());
        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "What about cash?");
        await user.click(screen.getByRole("button", { name: "Ask" }));
        await waitFor(() => expect(screen.getByText("Cash was stable.")).toBeInTheDocument());
        await user.click(screen.getAllByRole("button", { name: "Helpful" })[0]);

        expect(submitChatFeedbackApi).toHaveBeenCalledWith(7, true);
        expect(screen.getAllByRole("button", { name: "Helpful" })[0]).toBeDisabled();
        expect(screen.getAllByRole("button", { name: "Not helpful" })[0]).toBeDisabled();
        expect(screen.getAllByRole("button", { name: "Helpful" })[1]).not.toBeDisabled();
    });

    it("records not-helpful feedback for a later answer", async () => {
        vi.mocked(chatApi).mockResolvedValue({ data: { answer: "Cash declined." } } as never);
        vi.mocked(submitChatFeedbackApi).mockResolvedValue({} as never);
        const user = userEvent.setup();
        renderWidget();

        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "What changed?");
        await user.click(screen.getByRole("button", { name: "Ask" }));
        await waitFor(() => expect(screen.getByText("Cash declined.")).toBeInTheDocument());
        await user.click(screen.getByRole("button", { name: "Not helpful" }));

        expect(submitChatFeedbackApi).toHaveBeenCalledWith(7, false);
    });

    it("ignores a second submit while the first request is pending", async () => {
        let resolveRequest: ((value: { data: { answer: string } }) => void) | undefined;
        vi.mocked(chatApi).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }) as never);
        const user = userEvent.setup();
        renderWidget();

        await user.type(screen.getByPlaceholderText("e.g. How has total debt changed over the last few years?"), "What changed?");
        await user.click(screen.getByRole("button", { name: "Ask" }));
        await user.click(screen.getByRole("button", { name: "Ask" }));

        expect(chatApi).toHaveBeenCalledTimes(1);
        resolveRequest?.({ data: { answer: "The first answer." } });
        await waitFor(() => expect(screen.getByText("The first answer.")).toBeInTheDocument());
    });
});
