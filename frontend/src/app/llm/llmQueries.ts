import { useQuery } from "@tanstack/react-query";

import { getLlmProviderOperationsApi } from "../api/llm_api";

export const LLM_OPERATIONS_QUERY_KEY = ["llm", "operations"] as const;

export function useLlmProviderOperationsQuery() {
    return useQuery({
        queryKey: LLM_OPERATIONS_QUERY_KEY,
        queryFn: async () => (await getLlmProviderOperationsApi()).data,
        staleTime: 30_000,
    });
}
