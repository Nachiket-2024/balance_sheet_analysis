import { api } from "../sdk";

export type ReviewStatus = "draft" | "reviewed" | "approved" | "superseded";

export interface ReviewReport {
    id: number;
    company_id: number;
    created_by_email: string;
    title: string;
    status: ReviewStatus;
    years: number[];
    analysis: Record<string, unknown>;
    created_at: string;
    updated_at: string;
    notes: string | null;
}

export interface ReviewComment {
    id: number;
    review_report_id: number;
    author_email: string;
    body: string;
    created_at: string;
}

export const listCompanyReviewsApi = (companyId: number) => api.get<ReviewReport[]>(`/reviews/company/${companyId}`);

export const createReviewApi = (companyId: number, payload: { title: string; years?: number[]; notes?: string }) =>
    api.post<ReviewReport>(`/reviews/company/${companyId}`, payload);

export const updateReviewApi = (reportId: number, payload: { status: ReviewStatus; notes?: string }) =>
    api.patch<ReviewReport>(`/reviews/${reportId}`, payload);

export const listReviewCommentsApi = (reportId: number) => api.get<ReviewComment[]>(`/reviews/${reportId}/comments`);

export const addReviewCommentApi = (reportId: number, body: string) =>
    api.post<ReviewComment>(`/reviews/${reportId}/comments`, { body });

export const exportReviewHtmlApi = (reportId: number) =>
    api.get<Blob>(`/reviews/${reportId}/export.html`, { responseType: "blob" });
