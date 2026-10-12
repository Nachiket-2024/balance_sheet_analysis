import api from "@/api/axiosInstance";

export interface ChatRequest {
    company_id: number;
    years?: number[] | null;
    question: string;
}

export interface ChatResponse {
    answer: string;
}

export const chatApi = (payload: ChatRequest) => api.post<ChatResponse>("/llm/chat", payload);

export const submitChatFeedbackApi = (companyId: number, helpful: boolean) =>
    api.post("/llm/feedback", { helpful }, { params: { company_id: companyId } });

export interface LlmProviderOperationsSummary {
    provider: string;
    model: string;
    since: string;
    probes: number;
    reachable_probes: number;
    failed_probes: number;
    average_latency_ms: number | null;
    last_checked_at: string | null;
    last_error_code: string | null;
}

export const getLlmProviderOperationsApi = () =>
    api.get<LlmProviderOperationsSummary>("/llm/operations/admin");
