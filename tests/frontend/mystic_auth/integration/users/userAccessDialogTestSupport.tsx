import { render, screen, within } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import { useAuthStore } from "@/store/authStore";
import UsersPage from "@/users/UsersPage";
import { Toaster } from "@/ui/toaster/toaster";

// Shared fixtures/helpers for the User Access dialog's three test files
// (details, policies, permissions - split out of one 715-line file to stay
// under the repo's ~350-line target, see AGENTS.md). Each test file makes
// its own MockAdapter instance (axios-mock-adapter instances are
// independent, and `mock.reset()` in one file's beforeEach must never touch
// another file's handlers) but shares this module's fixtures/render helper.

export const mock = new MockAdapter(api);
const initialAuthState = useAuthStore.getState();

export function seed(permissions: string[], email = "admin@example.com") {
  useAuthStore.setState(initialAuthState, true);
  useAuthStore.getState().setAuthenticated(true);
  useAuthStore.getState().setProfile({
    name: "Test Admin",
    email,
    role: "admin",
    permissions,
    has_password: true,
    created_at: "2026-01-15T00:00:00Z",
    active_sessions: 1,
    brand_color: null,
  });
}

// withToaster: same opt-in as policies_page.test.tsx/users_page_bulk_actions.test.tsx
// - <Toaster/> isn't mounted by default, so a test that asserts toast text or
// an Undo button needs to opt in, or it'll never see anything render.
export function renderPage({ withToaster = false } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <UsersPage />
        {withToaster && <Toaster />}
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const SAMPLE_USERS = [
  {
    id: 1,
    name: "Admin User",
    email: "admin@example.com",
    role: "admin",
    is_verified: true,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Regular User",
    email: "user@example.com",
    role: "user",
    is_verified: true,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// Both action/grant tests need the catalog stubbed so there's something to
// toggle (see permissionQueries.ts's usePermissionCatalogQuery, GET
// /authorization/permissions/catalog). Includes one isDestructiveAction
// entry (users:assign_system_role, see destructiveActions.ts) to exercise
// the arm-then-confirm path.
export const PERMISSION_CATALOG = [
  {
    action: "users:list_all",
    resource_type: "users",
    description: "List and view any user's profile.",
  },
  {
    action: "users:read_own",
    resource_type: "users",
    description: "Read one's own user profile.",
  },
  {
    action: "users:assign_system_role",
    resource_type: "users",
    description: "Give someone the system role.",
  },
];

/** Opens the User Access dialog for "Regular User" via the given row
 * action button (View/Policies/Permissions), then switches to `tab` if
 * given - shared setup every test in all three files needs. */
export async function openAccessDialog(
  user: UserEvent,
  rowActionLabel: "View" | "Policies" | "Permissions",
  tab?: "Details" | "Policies" | "Permissions",
) {
  await screen.findByText("Regular User");
  const accessButtons = screen.getAllByRole("button", { name: rowActionLabel });
  await user.click(accessButtons[accessButtons.length - 1]);
  const dialog = await screen.findByRole("dialog");
  if (tab) {
    await user.click(within(dialog).getByRole("tab", { name: new RegExp(tab) }));
  }
  return dialog;
}
