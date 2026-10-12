/** Mirrors the backend escalation boundary for built-in and app-defined actions. */
export function canGrantAction(
    action: string,
    can: (action: string, resourceType?: string) => boolean,
): boolean {
    return can(action);
}

export function canGrantPolicy(
    policy: { actions: string[] },
    can: (action: string, resourceType?: string) => boolean,
): boolean {
    return policy.actions.every((action) => canGrantAction(action, can));
}
