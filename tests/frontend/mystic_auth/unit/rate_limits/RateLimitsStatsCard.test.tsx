import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RateLimitsStatsCard from "@/rate_limits/RateLimitsStatsCard";

describe("RateLimitsStatsCard", () => {
    it("renders server-computed summary counts", () => {
        render(
            <RateLimitsStatsCard
                isLoading={false}
                isError={false}
                activeTile="all"
                onFilterTotal={() => undefined}
                onFilterAtLimit={() => undefined}
                onFilterLoginLockouts={() => undefined}
                summary={{
                    total: 12,
                    at_limit: 4,
                    login_lockouts: 2,
                    by_endpoint: {},
                    by_scope: {},
                    truncated: false,
                }}
            />
        );

        expect(screen.getByText("Active counters")).toBeInTheDocument();
        expect(screen.getByText("At limit")).toBeInTheDocument();
        expect(screen.getByText("Login lockouts")).toBeInTheDocument();
        expect(screen.getByText("12")).toBeInTheDocument();
        expect(screen.getByText("4")).toBeInTheDocument();
        expect(screen.getByText("2")).toBeInTheDocument();
    });

    it("uses a dash when the summary request fails", () => {
        render(<RateLimitsStatsCard isLoading={false} isError summary={undefined} activeTile="all" onFilterTotal={() => undefined} onFilterAtLimit={() => undefined} onFilterLoginLockouts={() => undefined} />);

        expect(screen.getAllByText("–")).toHaveLength(3);
    });
});
