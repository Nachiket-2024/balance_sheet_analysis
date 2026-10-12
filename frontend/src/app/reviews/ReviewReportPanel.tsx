import React, { useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge, Button, Card, FormAlert, Input, LoadingState, toaster } from "../sdk";
import { exportReviewHtmlApi, type ReviewReport } from "../api/review_api";
import { useAddReviewCommentMutation, useCompanyReviewsQuery, useCreateReviewMutation, useReviewCommentsQuery, useUpdateReviewMutation } from "./reviewQueries";

const ReviewReportPanel: React.FC<{ companyId: number; years: number[] }> = ({ companyId, years }) => {
    const { t } = useTranslation("balance_sheets");
    const [title, setTitle] = useState("");
    const query = useCompanyReviewsQuery(companyId);
    const create = useCreateReviewMutation(companyId);
    const update = useUpdateReviewMutation(companyId);
    if (query.isLoading) return <LoadingState message={t("reviewsLoading")} />;
    if (query.isError) return <FormAlert status="error">{t("reviewsFailed")}</FormAlert>;
    const save = (event: React.FormEvent) => {
        event.preventDefault();
        if (!title.trim()) return;
        create.mutate({ title: title.trim(), years }, {
            onSuccess: () => { setTitle(""); toaster.create({ title: t("reviewSaved"), type: "success" }); },
            onError: () => toaster.create({ title: t("reviewSaveFailed"), type: "error" }),
        });
    };
    return <Card className="mb-6 p-5">
        <h2 className="text-lg font-semibold">{t("reviewsTitle")}</h2>
        <p className="mt-1 text-sm text-fg-muted">{t("reviewsDescription")}</p>
        <form className="mt-4 flex flex-wrap gap-2" onSubmit={save}>
            <Input className="min-w-64 flex-1" value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t("reviewTitlePlaceholder")} aria-label={t("reviewTitlePlaceholder")} />
            <Button type="submit" variant="brand" loading={create.isPending}>{t("saveReview")}</Button>
        </form>
        {!!query.data?.length && <div className="mt-5 flex flex-col gap-2">{query.data.map((report) => <ReviewRow key={report.id} companyId={companyId} report={report} update={update} t={t} />)}</div>}
    </Card>;
};

const ReviewRow: React.FC<{ companyId: number; report: ReviewReport; update: ReturnType<typeof useUpdateReviewMutation>; t: (key: string) => string }> = ({ companyId, report, update, t }) => {
    const [comment, setComment] = useState("");
    const comments = useReviewCommentsQuery(report.id);
    const addComment = useAddReviewCommentMutation(companyId, report.id);
    const exportHtml = async () => { const response = await exportReviewHtmlApi(report.id); const url = URL.createObjectURL(response.data); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `review-${report.id}.html`; anchor.click(); URL.revokeObjectURL(url); };
    const statusColor = report.status === "approved" || report.status === "reviewed" ? "green" : report.status === "superseded" ? "orange" : "gray";
    return <div className="rounded-xl border border-border-card bg-bg-canvas/40 p-4 shadow-card"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold">{report.title}</p><div className="mt-1.5 flex flex-wrap items-center gap-2"><span className="text-xs text-fg-muted">FY {report.years.join(", ")}</span><Badge colorPalette={statusColor} variant="subtle" size="sm">{t(`reviewStatus_${report.status}`)}</Badge></div></div><div className="flex flex-wrap gap-2">{report.status === "draft" && <Button size="sm" variant="outline" onClick={() => update.mutate({ reportId: report.id, status: "reviewed" })}>{t("markReviewed")}</Button>}{report.status === "reviewed" && <Button size="sm" variant="outline" onClick={() => update.mutate({ reportId: report.id, status: "approved" })}>{t("markApproved")}</Button>}<Button size="sm" variant="outline" onClick={exportHtml}>{t("exportReview")}</Button></div></div><div className="mt-4 border-t border-border-card pt-3"><p className="text-xs font-semibold uppercase tracking-wide text-fg-muted">{t("reviewComments")}</p>{comments.data?.map((item) => <p className="mt-2 rounded-lg bg-bg-surface px-3 py-2 text-sm" key={item.id}><span className="font-medium">{item.author_email}:</span> {item.body}</p>)}<form className="mt-3 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); if (!comment.trim()) return; addComment.mutate(comment.trim(), { onSuccess: () => setComment("") }); }}><Input className="min-w-56 flex-1" value={comment} onChange={(event) => setComment(event.target.value)} placeholder={t("commentPlaceholder")} aria-label={t("commentPlaceholder")} /><Button size="sm" type="submit" variant="outline">{t("addComment")}</Button></form></div></div>;
};

export default ReviewReportPanel;
