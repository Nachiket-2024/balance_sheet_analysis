import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { useDataTableSelection } from "@/ui/DataTable/DataTableSelection";

interface Row {
    id: number;
}

function SelectionHarness({ initial = new Set<number>(), disabled = new Set<number>() }) {
    const rows: Row[] = [{ id: 1 }, { id: 2 }, { id: 3 }];
    const [selected, setSelected] = useState<Set<string | number>>(initial);
    const selection = useDataTableSelection({
        rows,
        rowKey: (row) => row.id,
        selectedKeys: selected,
        onSelectionChange: setSelected,
        disabledKeys: disabled,
    });

    return (
        <div>
            <output data-testid="selected">{[...selected].join(",")}</output>
            <output data-testid="count">{selection.selectedOnScreenCount}</output>
            <output data-testid="all">{String(selection.isAllSelected)}</output>
            <output data-testid="some">{String(selection.isSomeSelected)}</output>
            <button onClick={() => selection.toggleRow(1)}>Toggle row 1</button>
            <button onClick={() => selection.toggleAll()}>Toggle all</button>
            <button onClick={() => selection.clearSelection()}>Clear</button>
        </div>
    );
}

describe("useDataTableSelection", () => {
    it("toggles individual rows and exposes partial selection state", async () => {
        const user = userEvent.setup();
        render(<SelectionHarness />);

        await user.click(screen.getByRole("button", { name: "Toggle row 1" }));
        expect(screen.getByTestId("selected")).toHaveTextContent("1");
        expect(screen.getByTestId("count")).toHaveTextContent("1");
        expect(screen.getByTestId("some")).toHaveTextContent("true");

        await user.click(screen.getByRole("button", { name: "Toggle row 1" }));
        expect(screen.getByTestId("selected")).toHaveTextContent("");
    });

    it("selects all eligible rows, then toggles them off", async () => {
        const user = userEvent.setup();
        render(<SelectionHarness disabled={new Set([3])} />);

        await user.click(screen.getByRole("button", { name: "Toggle all" }));
        expect(screen.getByTestId("selected")).toHaveTextContent("1,2");
        expect(screen.getByTestId("all")).toHaveTextContent("true");

        await user.click(screen.getByRole("button", { name: "Toggle all" }));
        expect(screen.getByTestId("selected")).toHaveTextContent("");
    });

    it("clears only visible eligible rows while preserving other selections", async () => {
        const user = userEvent.setup();
        render(<SelectionHarness initial={new Set([1, 9])} />);

        await user.click(screen.getByRole("button", { name: "Clear" }));
        expect(screen.getByTestId("selected")).toHaveTextContent("9");
    });
});
