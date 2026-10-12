import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import CopyLinkButton from "@/ui/feedback/CopyLinkButton";

describe("CopyLinkButton", () => {
    afterEach(() => vi.restoreAllMocks());

    it("copies the current path and encoded view parameters", async () => {
        const writeText = vi.fn().mockResolvedValue(undefined);
        Object.assign(navigator, { clipboard: { writeText } });
        Object.defineProperty(window, "location", {
            configurable: true,
            value: { origin: "https://auth.example.com", pathname: "/audit-log" },
        });

        const { container } = render(<CopyLinkButton buildParams={() => ({ category: "security", search: "a user" })} />);
        await userEvent.click(screen.getByRole("button", { name: /copy link to this view/i }));

        expect(writeText).toHaveBeenCalledWith(
            "https://auth.example.com/audit-log?category=security&search=a+user",
        );
        expect(screen.getByRole("button", { name: /copy link to this view/i })).toHaveTextContent("Copy link to this view");
        expect(container.querySelector(".lucide-check")).toBeInTheDocument();
    });

    it("returns to the link icon after transient feedback expires", async () => {
        vi.useFakeTimers();
        Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
        const { container } = render(<CopyLinkButton buildParams={() => ({ scope: "mine" })} />);

        fireEvent.click(screen.getByRole("button", { name: /copy link to this view/i }));
        expect(container.querySelector(".lucide-check")).toBeInTheDocument();

        act(() => vi.advanceTimersByTime(1500));
        expect(container.querySelector(".lucide-check")).toBeNull();
        vi.useRealTimers();
    });
});
