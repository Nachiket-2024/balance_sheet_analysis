import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { toaster } from "@/ui/toaster/toasterInstance";

import { mock, seed, renderPage, SAMPLE_USERS } from "./userAccessDialogTestSupport";

// Details tab and cross-tab keyboard navigation for the unified per-user
// Access dialog. Policies-tab and Permissions-tab coverage live in their own
// sibling files (users_page_access_dialog_policies.test.tsx /
// users_page_access_dialog_permissions.test.tsx) - split out of one 715-line
// file to keep each under the repo's ~350-line target, see AGENTS.md.

describe("UsersPage access dialog: details tab", () => {
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

  it("opens on the Details tab from the View row action, showing role/status", async () => {
    seed(["users:list_all"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByRole("tab", { name: /Details/ }),
    ).toHaveAttribute("aria-selected", "true");
    expect(within(dialog).getAllByText("user").length).toBeGreaterThan(0);
    expect(within(dialog).getByText("Verified")).toBeInTheDocument();
  });

  it("supports keyboard navigation across User Access tabs", async () => {
    seed(["users:list_all"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    const detailsTab = within(dialog).getByRole("tab", { name: /Details/ });
    const policiesTab = within(dialog).getByRole("tab", { name: /Policies/ });
    const permissionsTab = within(dialog).getByRole("tab", {
      name: /Permissions/,
    });

    expect(detailsTab).toHaveAttribute("tabindex", "0");
    expect(policiesTab).toHaveAttribute("tabindex", "-1");
    expect(detailsTab).toHaveAttribute(
      "aria-controls",
      "user-access-tabpanel-details",
    );

    detailsTab.focus();
    await user.keyboard("{ArrowRight}");
    await waitFor(() => expect(policiesTab).toHaveFocus());
    expect(policiesTab).toHaveAttribute("aria-selected", "true");
    expect(detailsTab).toHaveAttribute("tabindex", "-1");

    await user.keyboard("{End}");
    await waitFor(() => expect(permissionsTab).toHaveFocus());
    expect(permissionsTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Home}");
    await waitFor(() => expect(detailsTab).toHaveFocus());
    expect(detailsTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowLeft}");
    await waitFor(() => expect(permissionsTab).toHaveFocus());
    expect(permissionsTab).toHaveAttribute("aria-selected", "true");
  });

  it("shows recent access changes for a target user when the caller holds security_audit:read", async () => {
    seed(["users:list_all", "security_audit:read"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock
      .onGet("/audit/security-log/users/user%40example.com")
      .reply(200, [
        {
          id: 1,
          event_type: "policy_assigned",
          user_email: "user@example.com",
          success: true,
          created_at: "2026-02-01T00:00:00Z",
          event_metadata: { policy_name: "self_service", assigned_by: "admin@example.com" },
        },
      ]);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText(/self_service/),
    ).toBeInTheDocument();
  });

  it("shows an empty state when the target user has no recent access changes", async () => {
    seed(["users:list_all", "security_audit:read"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/audit/security-log/users/user%40example.com").reply(200, []);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText("No access changes yet."),
    ).toBeInTheDocument();
  });

  it("shows an error state when recent access changes fail to load", async () => {
    seed(["users:list_all", "security_audit:read"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/audit/security-log/users/user%40example.com").reply(500);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText(/Couldn't load recent access changes/i),
    ).toBeInTheDocument();
  });

  it("omits the recent-access-changes section entirely for a caller without security_audit:read on another user's row", async () => {
    seed(["users:list_all"]);
    mock.onGet("/users/").reply(200, SAMPLE_USERS);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    await user.click(viewButtons[viewButtons.length - 1]);

    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Verified");
    expect(
      within(dialog).queryByText(/recent access changes/i),
    ).toBeNull();
    // No request fired for data the caller isn't allowed to see at all.
    expect(
      mock.history.get.some((request) => request.url?.includes("/security-log/users/")),
    ).toBe(false);
  });

  it("shows recent access changes for the caller's own row via the self-service endpoint, no permission required", async () => {
    seed(["users:list_all"], "user@example.com");
    mock.onGet("/users/").reply(200, SAMPLE_USERS);
    mock.onGet("/audit/security-log/me").reply(200, [
      {
        id: 1,
        event_type: "permission_granted",
        user_email: "user@example.com",
        success: true,
        created_at: "2026-02-01T00:00:00Z",
        event_metadata: { action: "users:list_all", granted_by: "admin@example.com" },
      },
    ]);

    renderPage();
    const user = userEvent.setup();

    await screen.findByText("Regular User");
    const viewButtons = screen.getAllByRole("button", { name: "View" });
    // SAMPLE_USERS[1] (Regular User, user@example.com) is the caller's own
    // row here (seeded as currentUserEmail), so its View button is the
    // second one rendered.
    await user.click(viewButtons[1]);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByText(/users:list_all/),
    ).toBeInTheDocument();
  });
});
