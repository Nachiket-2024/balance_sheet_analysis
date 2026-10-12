import { useMemo, useState } from "react";

import type { PolicyRead } from "../api/policies_api";

/** Keeps a policy status switch responsive while its update is in flight. */
export function useOptimisticPolicyActivity(serverPolicies: PolicyRead[] | undefined) {
    const [optimisticActiveStates, setOptimisticActiveStates] = useState<Record<string, boolean>>({});
    const policies = useMemo(
        () => serverPolicies?.map((policy) => optimisticActiveStates[policy.name] === undefined
            ? policy
            : { ...policy, is_active: optimisticActiveStates[policy.name] }),
        [optimisticActiveStates, serverPolicies],
    );

    const setOptimisticActive = (policy: PolicyRead, isActive: boolean) => {
        setOptimisticActiveStates((current) => ({ ...current, [policy.name]: isActive }));
    };

    const rollbackOptimisticActive = (policyName: string) => {
        setOptimisticActiveStates((current) => {
            const next = { ...current };
            delete next[policyName];
            return next;
        });
    };

    return { policies, setOptimisticActive, rollbackOptimisticActive };
}
