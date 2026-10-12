import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RateLimitsFilterBar from "@/rate_limits/RateLimitsFilterBar";

function renderBar(overrides: Partial<React.ComponentProps<typeof RateLimitsFilterBar>> = {}) {
    const setEndpoint = vi.fn();
    const setIdentifier = vi.fn();
    const setScope = vi.fn();
    render(
        <RateLimitsFilterBar
            endpoint=""
            setEndpoint={setEndpoint}
            identifier=""
            setIdentifier={setIdentifier}
            scope=""
            setScope={setScope}
            isFetching={false}
            totalResults={undefined}
            totalCount={2}
            ipCount={0}
            accountCount={0}
            {...overrides}
        />
    );
    return { setEndpoint, setIdentifier, setScope };
}

describe("RateLimitsFilterBar", () => {
    it("lists endpoint and scope choices and sends selected values", async () => {
        const user = userEvent.setup();
        const { setEndpoint, setScope } = renderBar();

        await user.click(screen.getByRole("button", { name: "Filter by endpoint" }));
        await user.click(screen.getByRole("button", { name: "login" }));
        await user.click(within(screen.getByRole("radiogroup", { name: "Filter by scope" })).getByRole("radio", { name: "IP0" }));

        expect(setEndpoint).toHaveBeenCalledWith("login");
        expect(setScope).toHaveBeenCalledWith("ip");
    });

    it("renders active chips and clears each filter or all filters", async () => {
        const user = userEvent.setup();
        const { setEndpoint, setIdentifier, setScope } = renderBar({
            endpoint: "login",
            identifier: "203.0.113.7",
            scope: "account",
        });

        const clearButtons = screen.getAllByRole("button", { name: /Clear filters/ });
        expect(clearButtons).toHaveLength(4);

        await user.click(clearButtons[3]);
        expect(setEndpoint).toHaveBeenCalledWith("");
        expect(setIdentifier).toHaveBeenCalledWith("");
        expect(setScope).toHaveBeenCalledWith("");
    });

});
