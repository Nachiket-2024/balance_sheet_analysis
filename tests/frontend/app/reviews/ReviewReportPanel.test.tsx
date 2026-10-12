import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReviewReportPanel from "@app/reviews/ReviewReportPanel";

const mocks = vi.hoisted(() => ({
    addComment: vi.fn(),
    create: { mutate: vi.fn(), isPending: false },
    exportHtml: vi.fn(),
    query: { isLoading: false, isError: false, data: [] as Array<Record<string, unknown>> },
    update: { mutate: vi.fn(), isPending: false },
}));

const reports = () => [
    { id: 1, company_id: 7, created_by_email: "reviewer@example.com", title: "FY2024 review", status: "draft", years: [2024], analysis: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", notes: null },
    { id: 2, company_id: 7, created_by_email: "reviewer@example.com", title: "FY2023 review", status: "reviewed", years: [2023], analysis: {}, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", notes: null },
];

vi.mock("@app/reviews/reviewQueries", () => ({
    useCompanyReviewsQuery: () => mocks.query,
    useCreateReviewMutation: () => mocks.create,
    useUpdateReviewMutation: () => mocks.update,
    useReviewCommentsQuery: (reportId: number) => ({ data: reportId === 1 ? [{ id: 11, author_email: "auditor@example.com", body: "Check debt" }] : [] }),
    useAddReviewCommentMutation: () => ({ mutate: mocks.addComment, isPending: false }),
}));

vi.mock("@app/api/review_api", () => ({
    exportReviewHtmlApi: mocks.exportHtml,
}));

describe("ReviewReportPanel", () => {
    beforeEach(() => {
        mocks.query.isLoading = false;
        mocks.query.isError = false;
        mocks.query.data = reports();
        mocks.addComment.mockReset();
        mocks.create.mutate.mockReset();
        mocks.update.mutate.mockReset();
        mocks.exportHtml.mockReset();
    });
    it("keeps comment drafts isolated to their review report", async () => {
        const user = userEvent.setup();
        render(
            <ChakraProvider value={defaultSystem}>
                <ReviewReportPanel companyId={7} years={[2024, 2023]} />
            </ChakraProvider>,
        );

        const commentInputs = screen.getAllByPlaceholderText("Add a review comment");
        await user.type(commentInputs[0], "Only the first report");

        expect(commentInputs[0]).toHaveValue("Only the first report");
        expect(commentInputs[1]).toHaveValue("");
    });

    it("submits a trimmed comment for the report whose form was used", async () => {
        const user = userEvent.setup();
        render(
            <ChakraProvider value={defaultSystem}>
                <ReviewReportPanel companyId={7} years={[2024]} />
            </ChakraProvider>,
        );

        const commentInputs = screen.getAllByPlaceholderText("Add a review comment");
        await user.type(commentInputs[1], "  Needs follow-up  ");
        await user.click(screen.getAllByRole("button", { name: "Comment" })[1]);

        expect(mocks.addComment).toHaveBeenCalledWith("Needs follow-up", expect.anything());
    });

    it("renders loading and failure states", () => {
        mocks.query.isLoading = true;
        const { rerender } = render(<ChakraProvider value={defaultSystem}><ReviewReportPanel companyId={7} years={[2024]} /></ChakraProvider>);
        expect(screen.getByText("Loading saved reviews...")).toBeInTheDocument();
        mocks.query.isLoading = false;
        mocks.query.isError = true;
        rerender(<ChakraProvider value={defaultSystem}><ReviewReportPanel companyId={7} years={[2024]} /></ChakraProvider>);
        expect(screen.getByText("Failed to load saved reviews")).toBeInTheDocument();
    });

    it("validates and submits a trimmed new review title", async () => {
        const user = userEvent.setup();
        render(<ChakraProvider value={defaultSystem}><ReviewReportPanel companyId={7} years={[2024, 2023]} /></ChakraProvider>);
        const title = screen.getByLabelText("Review title");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        expect(mocks.create.mutate).not.toHaveBeenCalled();
        await user.type(title, "  Annual review  ");
        await user.click(screen.getByRole("button", { name: "Save review" }));
        expect(mocks.create.mutate).toHaveBeenCalledWith({ title: "Annual review", years: [2024, 2023] }, expect.anything());
    });

    it("updates statuses and exports the selected report", async () => {
        const user = userEvent.setup();
        const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:review");
        const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
        mocks.exportHtml.mockResolvedValue({ data: new Blob(["<html />"], { type: "text/html" }) });
        render(<ChakraProvider value={defaultSystem}><ReviewReportPanel companyId={7} years={[2024]} /></ChakraProvider>);
        await user.click(screen.getByRole("button", { name: "Mark reviewed" }));
        await user.click(screen.getByRole("button", { name: "Approve" }));
        expect(mocks.update.mutate).toHaveBeenNthCalledWith(1, { reportId: 1, status: "reviewed" });
        expect(mocks.update.mutate).toHaveBeenNthCalledWith(2, { reportId: 2, status: "approved" });
        await user.click(screen.getAllByRole("button", { name: "Export HTML" })[0]);
        await vi.waitFor(() => expect(mocks.exportHtml).toHaveBeenCalledWith(1));
        expect(createObjectURL).toHaveBeenCalled();
        expect(revokeObjectURL).toHaveBeenCalledWith("blob:review");
        createObjectURL.mockRestore();
        revokeObjectURL.mockRestore();
    });
});
