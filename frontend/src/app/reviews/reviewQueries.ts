import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addReviewCommentApi, createReviewApi, listCompanyReviewsApi, listReviewCommentsApi, updateReviewApi, type ReviewStatus } from "../api/review_api";

export const companyReviewsQueryKey = (companyId: number) => ["reviews", companyId] as const;
export const reviewCommentsQueryKey = (reportId: number) => ["review-comments", reportId] as const;

export function useCompanyReviewsQuery(companyId: number, options?: { enabled?: boolean }) {
    return useQuery({
        queryKey: companyReviewsQueryKey(companyId),
        queryFn: async () => (await listCompanyReviewsApi(companyId)).data,
        enabled: options?.enabled,
    });
}

export function useCreateReviewMutation(companyId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (payload: { title: string; years?: number[]; notes?: string }) => createReviewApi(companyId, payload),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: companyReviewsQueryKey(companyId) }),
    });
}

export function useUpdateReviewMutation(companyId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ reportId, status }: { reportId: number; status: ReviewStatus }) => updateReviewApi(reportId, { status }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: companyReviewsQueryKey(companyId) }),
    });
}

export function useReviewCommentsQuery(reportId: number) {
    return useQuery({
        queryKey: reviewCommentsQueryKey(reportId),
        queryFn: async () => (await listReviewCommentsApi(reportId)).data,
    });
}

export function useAddReviewCommentMutation(companyId: number, reportId: number) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (body: string) => addReviewCommentApi(reportId, body),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: reviewCommentsQueryKey(reportId) });
            queryClient.invalidateQueries({ queryKey: companyReviewsQueryKey(companyId) });
        },
    });
}
