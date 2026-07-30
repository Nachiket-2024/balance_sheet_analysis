# RBAC Quickstart: Role-Shaped Policies Without Conditions

[Common Patterns](common-patterns.md) covers modeling *hierarchies* on top of PBAC. This page is for the opposite, simpler need: your access model really is just "everyone with role X gets exactly these actions, no per-resource scoping", i.e. plain RBAC, and PBAC's full generality (conditions, `resource_attributes`, time/network/date-range checks) is more machinery than you need for it.

You don't need a different mechanism for this. This template doesn't ship a separate RBAC engine alongside PBAC, and it doesn't need to: a **policy with no `conditions` at all is already RBAC**. This template's own three seeded baseline policies (`self_service`, `user_administration`, `system_superuser`, see [Policy JSON Examples](policy-examples.md)) are exactly that shape already: one unconditioned policy per "role", each just an action list. Building your own roles this way costs nothing extra: same tables, same evaluator, same audit log, same `require_authorization(...)` on every route.

## The recipe

1. **One policy per role**, `conditions` omitted (or explicitly `null`): an unconditioned policy always evaluates to "granted" for anyone holding it, since [`condition_evaluation_service.py`](../authorization/architecture.md#condition-evaluation-service) has nothing to check:

   ```json
   {
     "name": "role_editor",
     "description": "Can view and edit documents",
     "actions": ["documents:view", "documents:edit"],
     "resource_type": "documents"
   }
   ```

   ```json
   {
     "name": "role_viewer",
     "description": "Read-only access to documents",
     "actions": ["documents:view"],
     "resource_type": "documents"
   }
   ```

   Create either via `POST /authorization/policies` (see [Writing and Testing Policies](writing-testing-policies.md#policy-creation-workflow)), the `/policies` UI, or the CLI script below.

2. **Assign it** to whichever users should hold that role, via `POST /authorization/users/{email}/policies` (or the UI). A user can hold more than one role-policy at once; PBAC evaluates every held policy, so someone with both `role_editor` and `role_viewer` simply has the union of both action lists.

3. **Routes stay identical either way.** `require_authorization("documents:edit", "documents")` doesn't know or care whether the policy that ends up granting it has conditions or not; see [Adding New Permissions](adding-permissions.md) for the route side, which is unaffected by which policy *shape* you choose.

## `users.role` still doesn't grant anything

This pattern doesn't change the one rule the rest of this template's authorization docs already state repeatedly: `users.role` is display/grouping metadata only, never read by the authorization service, evaluator, or condition handlers (see [Adding New Permissions: Roles vs. policies](adding-permissions.md#roles-vs-policies)). "RBAC-shaped" here describes the *policy's* shape (unconditioned, one per role), not a return to role-column checks anywhere in the request path. If you want the UI to visually group users by their intended role, that's exactly what `users.role` remains useful for (e.g. showing "Editor" next to a name); it's just never consulted to decide whether a request is allowed.

## Optional: a CLI script for this

`backend/mystic_auth/scripts/create_rbac_policies.py`, same shape as [`create_system_user.py`](../authentication/system-superuser.md), interactive and CLI-only:

```bash
python -m mystic_auth.scripts.create_rbac_policies
```

Prompts for a role name, resource type, and a comma-separated action list, then creates one unconditioned policy named `role_<role>`. Idempotent by name: running it again for a role that already has a policy prints the existing action list and makes no changes, rather than silently overwriting it (edit via `PUT /authorization/policies/{id}` or the UI instead). Entirely optional: everything it does is also just one `POST /authorization/policies` call, so skip it if you'd rather create role-policies through the API/UI directly.

## When you actually do want PBAC's conditions

If "everyone with this role" stops being precise enough (e.g. "editors, but only for documents they own" or "editors, but only during business hours"), that's exactly what conditions are for, and you don't have to migrate away from anything: add a `conditions` block to the same policy (or a more specific one) and keep going. See [Policy JSON Examples](policy-examples.md) for conditioned policies, [Common Patterns](common-patterns.md) for hierarchy-shaped scoping, and the [Condition Schema Reference](condition-schema-reference.md) for the full list of what's available.
