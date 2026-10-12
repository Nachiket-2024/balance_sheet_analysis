import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LlmOperationsPage from "@app/llm/LlmOperationsPage";
import { getLlmProviderOperationsApi } from "@app/api/llm_api";

vi.mock("@app/api/llm_api", () => ({ getLlmProviderOperationsApi: vi.fn() }));

function renderPage() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <ChakraProvider value={defaultSystem}>
                <LlmOperationsPage />
            </ChakraProvider>
        </QueryClientProvider>,
    );
}

describe("LlmOperationsPage", () => {
    it("renders bounded provider telemetry", async () => {
        vi.mocked(getLlmProviderOperationsApi).mockResolvedValue({
            data: {
                provider: "groq",
                model: "llama-3.1-8b-instant",
                since: "2026-10-02T00:00:00Z",
                probes: 10,
                reachable_probes: 8,
                failed_probes: 2,
                average_latency_ms: 120.5,
                last_checked_at: "2026-10-03T00:00:00Z",
                last_error_code: "provider_unreachable",
            },
        } as never);

        renderPage();

        await waitFor(() => expect(screen.getByText("LLM provider operations")).toBeInTheDocument());
        expect(screen.getByText("groq")).toBeInTheDocument();
        expect(screen.getByText("80%")).toBeInTheDocument();
        expect(screen.getByText("120.5 ms")).toBeInTheDocument();
        expect(screen.getByText("provider_unreachable")).toBeInTheDocument();
    });

    it("shows an error when telemetry cannot be loaded", async () => {
        vi.mocked(getLlmProviderOperationsApi).mockRejectedValue(new Error("forbidden"));

        renderPage();

        await waitFor(() => expect(screen.getByText("Provider operations are unavailable.")).toBeInTheDocument());
    });
});
