import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { toaster } from "@/ui/toaster/toasterInstance";

import { mock, seed, renderPage, SAMPLE_USERS } from "./userAccessDialogTestSupport";

// Policies tab of the unified per-user Access dialog: instant assign/revoke
// of a whole policy, with Undo. Per-action revoke and the
// already-covered-so-disabled case live in
// users_page_access_dialog_policy_actions.test.tsx; Details/keyboard-nav and
// Permissions-tab coverage live in their own sibling files too - split out
// of one 715-line file to keep each under the repo's ~350-line target, see
// AGENTS.md.

describe("UsersPage access dialog: policies tab", () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton that outlives each test's render
    // tree; clear it so a leftover toast (every instant toggle creates one)
    // can't leak into the next test - see policies_page.test.tsx's identical
    // cleanup.
    await act(async () => {
      toaster.remove();
    });
  });

  it("opens straight on the Policies tab from the Policies row action, and instant-assigns a not-yet-assigned policy with Undo", async () => {
    seed([
      "users:list_all",
      "policies:read",
      "policies:assign",
      "policies:revoke",
      "reports:view",
    ]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/authorization/policies").reply(200, [
      {
        id: 1,
        name: "self_service",
        description: "",
        actions: ["users:read_own"],
        resource_type: "users",
        conditions: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
      },
      {
        id: 2,
        name: "reporting",
        description: "",
        actions: ["reports:view"],
        resource_type: "reports",
        conditions: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
      },
    ]);
    mock.onGet("/authorization/users/user%40example.com/policies").reply(200, {
      user_email: "user@example.com",
      policies: [
        {
          id: 1,
          name: "self_service",
          description: "",
          actions: ["users:read_own"],
          resource_type: "users",
          conditions: null,
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          created_by: null,
        },
      ],
    });
    mock.onPost("/authorization/users/user%40example.com/policies").reply(200);
    mock
      .onDelete("/authorization/users/user%40example.com/policies/reporting")
      .reply(204);

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", {
      name: "Policies",
    });
    await user.click(accessButtons[accessButtons.length - 1]);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("tab", {
        name: /Policies/,
      }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("tab", { name: /Policies/ }),
    ).toHaveAttribute("aria-selected", "true");
    await within(dialog).findByText("self_service");
    await within(dialog).findByText("reporting");

    // Not-yet-assigned policy: a click assigns instantly, no form to fill in.
    await user.click(within(dialog).getByRole("switch", { name: "reporting" }));
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      policy_name: "reporting",
    });
    expect(await screen.findByText(/Assigned "reporting"/)).toBeInTheDocument();
    const assignUndo = screen.getAllByRole("button", { name: "Undo" }).at(-1)!;
    await user.click(assignUndo);
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(await screen.findByText(/Removed "reporting"/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("instant-revokes an already-assigned policy with Undo, no confirm dialog", async () => {
    // Revoking is a single click here, unlike the old dialog's ConfirmDialog:
    // instant + Undo is the whole point of this dialog (see its docstring).
    // Only the per-action revoke-from-a-still-assigned-policy path keeps a
    // confirm, since that one has no Undo the backend can actually honor.
    seed(["users:list_all", "users:read_own", "policies:read", "policies:revoke"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/authorization/policies").reply(200, [
      {
        id: 1,
        name: "self_service",
        description: "",
        actions: ["users:read_own"],
        resource_type: "users",
        conditions: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
      },
    ]);
    mock.onGet("/authorization/users/user%40example.com/policies").reply(200, {
      user_email: "user@example.com",
      policies: [
        {
          id: 1,
          name: "self_service",
          description: "",
          actions: ["users:read_own"],
          resource_type: "users",
          conditions: null,
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          created_by: null,
        },
      ],
    });
    mock
      .onDelete("/authorization/users/user%40example.com/policies/self_service")
      .reply(204);
    mock.onPost("/authorization/users/user%40example.com/policies").reply(200);

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", {
      name: "Policies",
    });
    await user.click(accessButtons[accessButtons.length - 1]);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("tab", {
        name: /Policies/,
      }),
    );

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("self_service");

    await user.click(
      within(dialog).getByRole("switch", { name: "Revoke self_service" }),
    );
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(
      await screen.findByText(/Removed "self_service"/),
    ).toBeInTheDocument();
    const revokeUndo = screen.getAllByRole("button", { name: "Undo" }).at(-1)!;
    await user.click(revokeUndo);
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(
      await screen.findByText(/Assigned "self_service"/),
    ).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
