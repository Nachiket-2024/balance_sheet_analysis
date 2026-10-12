import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { toaster } from "@/ui/toaster/toasterInstance";

import { mock, seed, renderPage, SAMPLE_USERS } from "./userAccessDialogTestSupport";

// Policies tab, per-action revoke and the already-covered-so-disabled case.
// Split out of users_page_access_dialog_policies.test.tsx (assign/revoke a
// whole policy) to keep each file under the repo's ~350-line target, see
// AGENTS.md.

describe("UsersPage access dialog: policy actions", () => {
  beforeEach(() => {
    mock.reset();
  });

  afterEach(async () => {
    // toaster is a module-level singleton that outlives each test's render
    // tree; clear it so a leftover toast can't leak into the next test.
    await act(async () => {
      toaster.remove();
    });
  });

  it("expands a policy to reveal its actions and revokes just one of them immediately", async () => {
    seed([
      "users:list_all",
      "policies:read",
      "policies:revoke",
      "permissions:grant",
    ]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/authorization/policies").reply(200, [
      {
        id: 1,
        name: "reporting",
        description: "",
        actions: ["reports:view", "reports:export"],
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
          name: "reporting",
          description: "",
          actions: ["reports:view", "reports:export"],
          resource_type: "reports",
          conditions: null,
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          created_by: null,
        },
      ],
    });
    mock
      .onPost(
        "/authorization/users/user%40example.com/policies/reporting/revoke-action",
      )
      .reply(200);

    renderPage();
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
    await within(dialog).findByText("reporting");

    // Actions aren't shown until the policy row is expanded.
    expect(within(dialog).queryByText("View reports")).toBeNull();
    await user.click(
      within(dialog).getByRole("button", {
        name: /Show reporting's individual actions/,
      }),
    );
    await within(dialog).findByText("View reports");
    expect(within(dialog).getByText("Export reports")).toBeInTheDocument();

    await user.click(within(dialog).getByText("View reports"));
    await waitFor(() => expect(mock.history.post.length).toBe(1));
    expect(
      screen.queryByText(/Revoke "View reports" from user@example.com/),
    ).toBeNull();
    expect(mock.history.post[0].url).toBe(
      "/authorization/users/user%40example.com/policies/reporting/revoke-action",
    );
    expect(JSON.parse(mock.history.post[0].data)).toEqual({
      action: "reports:view",
    });
  });

  it("disables an unassigned policy whose actions are already covered by a policy the user holds", async () => {
    // "reporting-viewer" grants only reports:view, already covered by
    // "reporting" (reports:view + reports:export) this user already holds -
    // assigning it would add nothing new, same reasoning the Permissions tab
    // already applies per-action (isAlreadyEffectivelyGranted/onlyViaPolicy).
    seed([
      "users:list_all",
      "policies:read",
      "policies:assign",
      "policies:revoke",
      "reports:view",
      "invoices:read",
    ]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/authorization/policies").reply(200, [
      {
        id: 1,
        name: "reporting",
        description: "",
        actions: ["reports:view", "reports:export"],
        resource_type: "reports",
        conditions: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
      },
      {
        id: 2,
        name: "reporting-viewer",
        description: "",
        actions: ["reports:view"],
        resource_type: "reports",
        conditions: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
      },
      {
        id: 3,
        name: "billing",
        description: "",
        actions: ["invoices:read"],
        resource_type: "invoices",
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
          name: "reporting",
          description: "",
          actions: ["reports:view", "reports:export"],
          resource_type: "reports",
          conditions: null,
          is_active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          created_by: null,
        },
      ],
    });

    renderPage();
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
    await within(dialog).findByText("reporting-viewer");

    expect(
      within(dialog).getByRole("switch", { name: "reporting-viewer" }),
    ).toBeDisabled();
    expect(
      within(dialog).getByRole("switch", { name: "billing" }),
    ).toBeEnabled();
  });
});
