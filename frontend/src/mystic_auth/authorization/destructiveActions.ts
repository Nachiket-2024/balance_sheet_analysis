/** Actions severe enough to flag red wherever they're displayed: account
 * deactivation/deletion, privilege escalation (assigning the system role),
 * deleting or revoking a policy/permission grant, and clearing a live
 * rate-limit counter. Explicit list, not a naming heuristic (e.g. "any
 * action starting with delete_") - a heuristic would mis-flag a merely-
 * reversible write like `reactivate` just for sharing a verb, and silently
 * miss a future destructive action that doesn't match the pattern. Full
 * "resource:action" strings, not bare verbs: every real action (PERMISSIONS
 * in permissions.ts, the permission catalog, PolicyRead.actions) is
 * resource-prefixed, e.g. "users:delete_any", never a bare "delete_any" - a
 * bare-verb set here would never match anything. Mirrors PERMISSIONS in
 * permissions.ts; update this alongside any new destructive action added
 * there.
 *
 * Matches design/permissions.html's SENSITIVE pattern (delete|purge|void|
 * refund|revoke|reset|transfer|archive|rotate|deactivate|assign_system_role)
 * applied to this app's real catalog - this file previously only had the
 * three "users:*" entries, which missed policies:delete, policies:revoke,
 * permissions:revoke and rate_limits:reset even though each matches that
 * same pattern and is just as consequential (deleting a policy, pulling a
 * grant out from under a user, wiping a live rate-limit counter). */
const DESTRUCTIVE_ACTIONS = new Set([
    "users:deactivate_any",
    "users:delete_any",
    "users:assign_system_role",
    "policies:delete",
    "policies:revoke",
    "permissions:revoke",
    "rate_limits:reset",
]);

export function isDestructiveAction(action: string): boolean {
    return DESTRUCTIVE_ACTIONS.has(action);
}
