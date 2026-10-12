import { beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import { addReviewCommentApi, createReviewApi, exportReviewHtmlApi, listCompanyReviewsApi, listReviewCommentsApi, updateReviewApi } from "@app/api/review_api";

const mock = new MockAdapter(api);

describe("review report API", () => {
    beforeEach(() => mock.reset());

    it("lists saved company reviews", async () => {
        mock.onGet("/reviews/company/7").reply(200, [{ id: 1, company_id: 7, status: "draft" }]);
        const response = await listCompanyReviewsApi(7);
        expect(response.data[0]).toMatchObject({ company_id: 7, status: "draft" });
    });

    it("creates and updates a review", async () => {
        mock.onPost("/reviews/company/7").reply(201, { id: 1, title: "FY review" });
        mock.onPatch("/reviews/1").reply(200, { id: 1, status: "reviewed" });

        const created = await createReviewApi(7, { title: "FY review", years: [2023] });
        const updated = await updateReviewApi(1, { status: "reviewed" });

        expect(created.data.title).toBe("FY review");
        expect(updated.data.status).toBe("reviewed");
    });

    it("lists and adds scoped comments", async () => {
        mock.onGet("/reviews/1/comments").reply(200, [{ id: 2, body: "Check debt" }]);
        mock.onPost("/reviews/1/comments").reply(201, { id: 2, body: "Check debt" });

        const comments = await listReviewCommentsApi(1);
        const added = await addReviewCommentApi(1, "Check debt");

        expect(comments.data[0].body).toBe("Check debt");
        expect(added.data.body).toBe("Check debt");
    });

    it("downloads an exported review as HTML", async () => {
        mock.onGet("/reviews/1/export.html").reply(200, "<html />");
        const response = await exportReviewHtmlApi(1);
        expect(response.config.responseType).toBe("blob");
        expect(response.data).toBe("<html />");
    });
});
