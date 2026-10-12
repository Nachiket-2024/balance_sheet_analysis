import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { toaster } from "@/ui/toaster/toasterInstance";

import { mock, seed, renderPage, SAMPLE_USERS, PERMISSION_CATALOG } from "./userAccessDialogTestSupport";

// Permissions tab of the unified per-user Access dialog: instant grant/
// revoke with Undo, and sensitive-action grants (only enabled when the
// caller already holds the action themselves). Details/keyboard-nav and
// Policies-tab coverage live in their own sibling files - split out of one
// 715-line file to keep each under the repo's ~350-line target, see
// AGENTS.md.

describe("UsersPage access dialog: permissions tab", () => {
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

  it("opens straight on the Permissions tab and instant-grants a not-yet-held direct permission with Undo", async () => {
    seed(["users:list_all", "permissions:read", "permissions:grant"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock
      .onGet("/authorization/permissions/catalog")
      .reply(200, PERMISSION_CATALOG);
    mock
      .onGet("/authorization/users/user%40example.com/permissions")
      .reply(200, {
        user_email: "user@example.com",
        permissions: [],
      });
    mock
      .onPost("/authorization/users/user%40example.com/permissions")
      .reply(200);

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", {
      name: "Permissions",
    });
    await user.click(accessButtons[accessButtons.length - 1]);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("tab", {
        name: /Permissions/,
      }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("tab", { name: /Permissions/ }),
    ).toHaveAttribute("aria-selected", "true");
    await within(dialog).findByText("List and view any user's profile.");

    // Narrow to this one action first: every not-yet-granted, non-destructive
    // row shares the same "Give this permission directly" aria-label, so
    // without this the checkbox query below would be ambiguous.
    await user.type(
      within(dialog).getByPlaceholderText("Search permissions"),
      "list_all",
    );
    await within(dialog).findByText("List and view any user's profile.");
    expect(
      within(dialog).queryByText("Read one's own user profile."),
    ).toBeNull();

    // The permission row itself is the toggle target; the copy icon remains a
    // separate, explicit copy-only control.
    await user.click(
      within(dialog).getByText("List and view any user's profile."),
    );
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      action: "users:list_all",
      resource_type: "users",
    });
    expect(
      await screen.findByText(/Gave "users:list_all"/),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: "Undo" }),
    ).toBeInTheDocument();
    // The refresh must not collapse the resource group or lose the row that
    // was just changed from view.
    expect(
      within(dialog).getByText("List and view any user's profile."),
    ).toBeInTheDocument();
  });

  it("instant-revokes an already-granted direct permission with Undo, no confirm dialog", async () => {
    seed(["users:list_all", "users:read_own", "permissions:read", "permissions:revoke"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock
      .onGet("/authorization/permissions/catalog")
      .reply(200, PERMISSION_CATALOG);
    mock
      .onGet("/authorization/users/user%40example.com/permissions")
      .reply(200, {
        user_email: "user@example.com",
        permissions: [
          {
            id: 1,
            action: "users:read_own",
            resource_type: "users",
            conditions: null,
            is_active: true,
            assigned_by: null,
          },
        ],
      });
    mock
      .onDelete(/\/authorization\/users\/user%40example\.com\/permissions\//)
      .reply(200);

    renderPage({ withToaster: true });
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", {
      name: "Permissions",
    });
    await user.click(accessButtons[accessButtons.length - 1]);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("tab", {
        name: /Permissions/,
      }),
    );

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Read one's own user profile.");

    // Already-granted action: a single click revokes it, still enforced
    // server-side regardless of what the UI allows.
    await user.click(
      within(dialog).getByRole("switch", { name: "Remove this direct grant" }),
    );
    await waitFor(() => expect(mock.history.delete.length).toBe(1));
    expect(
      await screen.findByText(/Removed "users:read_own"/),
    ).toBeInTheDocument();
  });

  it("grants a sensitive action on one click when the caller already holds it", async () => {
    seed(["users:list_all", "users:assign_system_role", "permissions:read", "permissions:grant"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock
      .onGet("/authorization/permissions/catalog")
      .reply(200, PERMISSION_CATALOG);
    mock
      .onGet("/authorization/users/user%40example.com/permissions")
      .reply(200, {
        user_email: "user@example.com",
        permissions: [],
      });
    mock
      .onPost("/authorization/users/user%40example.com/permissions")
      .reply(200);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", {
      name: "Permissions",
    });
    await user.click(accessButtons[accessButtons.length - 1]);
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("tab", {
        name: /Permissions/,
      }),
    );

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Give someone the system role.");

    const sensitiveRow = within(dialog).getByText("Give someone the system role.").closest("div.flex")?.parentElement?.parentElement;
    expect(sensitiveRow).not.toBeNull();
    await user.click(within(sensitiveRow!).getByRole("switch", { name: "Give this permission directly" }));
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      action: "users:assign_system_role",
      resource_type: "users",
    });
  });

  it("disables a sensitive grant when the caller does not already hold that permission", async () => {
    seed(["users:list_all", "permissions:read", "permissions:grant"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/authorization/permissions/catalog").reply(200, PERMISSION_CATALOG);
    mock.onGet("/authorization/users/user%40example.com/permissions").reply(200, {
      user_email: "user@example.com",
      permissions: [],
    });

    renderPage();
    const user = userEvent.setup();
    await screen.findByText("Regular User");
    const accessButtons = screen.getAllByRole("button", { name: "Permissions" });
    await user.click(accessButtons[accessButtons.length - 1]);
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("tab", { name: /Permissions/ }));

    const restrictedSwitches = await within(dialog).findAllByRole("switch", {
      name: "You must already hold this permission before you can grant or remove it.",
    });
    expect(restrictedSwitches.length).toBeGreaterThan(0);
    expect(restrictedSwitches.every((switchElement) => (switchElement as HTMLButtonElement).disabled)).toBe(true);
    expect(mock.history.post).toHaveLength(0);
  });
});
