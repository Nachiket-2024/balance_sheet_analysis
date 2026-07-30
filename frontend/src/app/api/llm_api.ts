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
