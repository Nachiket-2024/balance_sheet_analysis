import { useAuthorization } from "./useAuthorization";

// See useAuthorization's `can` for the full contract (including why
// resourceType doesn't currently narrow the check, and why an array
// argument means "any of").
export function useCan(action: string | string[], resourceType?: string): boolean {
    return useAuthorization().can(action, resourceType);
}

// Alias for call sites that read more naturally as "is the caller
// authorized for X" than "can the caller do X"; same hook either way.
export const useAuthorized = useCan;
