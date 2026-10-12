import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import PasswordInput from "@/ui/inputs/PasswordInput";
import StatTile from "@/ui/display/StatTile";

describe("PasswordInput", () => {
    it("starts masked and toggles visibility without changing the input value", async () => {
        const user = userEvent.setup();
        render(<PasswordInput aria-label="Password" defaultValue="correct horse" />);
        const input = screen.getByLabelText("Password");
        const showButton = screen.getByRole("button", { name: /show password/i });
        expect(input).toHaveAttribute("type", "password");
        expect(input).toHaveValue("correct horse");
        expect(showButton).not.toHaveAttribute("tabindex", "-1");
        expect(showButton).toHaveClass("focus-visible:ring-2");

        await user.click(screen.getByRole("button", { name: /show password/i }));
        expect(input).toHaveAttribute("type", "text");
        expect(screen.getByRole("button", { name: /hide password/i })).toBeInTheDocument();

        await user.click(screen.getByRole("button", { name: /hide password/i }));
        expect(input).toHaveAttribute("type", "password");
        expect(input).toHaveValue("correct horse");
    });
});

describe("StatTile", () => {
    it("renders a loading skeleton instead of exposing stale numeric data", () => {
        render(<StatTile label="Users" value={42} isLoading />);

        expect(screen.queryByText("42")).toBeNull();
        expect(screen.getByText("Users")).toBeInTheDocument();
        expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
    });

    it("renders a formatted value and custom hex color", () => {
        render(<StatTile label="Users" value={1234} isLoading={false} color="#123456" />);

        const value = screen.getByText("1234");
        expect(value).toHaveStyle({ color: "#123456" });
        expect(value).toHaveClass("text-3xl");
    });

    it("uses a button with the default filter label when clickable", async () => {
        const onClick = vi.fn();
        render(<StatTile label="Active users" value={7} isLoading={false} onClick={onClick} />);

        const tile = screen.getByRole("button", { name: "Filter: Active users" });
        await userEvent.click(tile);
        expect(onClick).toHaveBeenCalledOnce();
    });

    it("honors an explicit accessible label for a clickable tile", () => {
        render(
            <StatTile
                label="Deactivated"
                value={2}
                isLoading={false}
                onClick={() => undefined}
                ariaLabel="Show deactivated users"
            />,
        );

        expect(screen.getByRole("button", { name: "Show deactivated users" })).toBeInTheDocument();
    });
});
