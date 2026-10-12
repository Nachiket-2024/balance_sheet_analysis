import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DetailsDrawer from "@/ui/display/DetailsDrawer";

function renderDrawer() {
  const onClose = vi.fn();
  const onPrevious = vi.fn();
  const onNext = vi.fn();
  render(
    <DetailsDrawer
      isOpen
      onClose={onClose}
      title="Audit entry"
      position="2 of 3"
      onPrevious={onPrevious}
      onNext={onNext}
      canGoPrevious
      canGoNext
    >
      <p>Entry details</p>
      <input aria-label="Notes" />
    </DetailsDrawer>
  );
  return { onClose, onPrevious, onNext };
}

describe("DetailsDrawer keyboard navigation", () => {
  it("moves through entries with arrows and preserves j/k shortcuts", async () => {
    const user = userEvent.setup();
    const { onPrevious, onNext } = renderDrawer();

    await user.keyboard("{ArrowRight}");
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{ArrowLeft}");
    await user.keyboard("{ArrowUp}");
    await user.keyboard("j");
    await user.keyboard("k");

    expect(onNext).toHaveBeenCalledTimes(3);
    expect(onPrevious).toHaveBeenCalledTimes(3);
  });

  it("does not hijack arrow keys while typing in a drawer field", async () => {
    const user = userEvent.setup();
    const { onPrevious, onNext } = renderDrawer();
    const notes = screen.getByRole("textbox", { name: "Notes" });

    await user.click(notes);
    await user.keyboard("{ArrowRight}{ArrowLeft}jk");

    expect(onNext).not.toHaveBeenCalled();
    expect(onPrevious).not.toHaveBeenCalled();
  });
});
