import React from "react";
import { useTranslation } from "react-i18next";

import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import LoadingState from "../ui/feedback/LoadingState";
import FormAlert from "../ui/feedback/FormAlert";
import { useMyPoliciesQuery } from "../policies/queries/policyQueries";
import { useMyPermissionsQuery } from "../policies/queries/permissionQueries";
import { buildEffectiveGrantsWithSource, dedupeAgainstWildcards } from "../policies/logic/effectiveGrants";
import AccessResourceCards from "../users/dialogs/AccessResourceCards";
import { formatResourceTypeLabel } from "../policies/policyCardHelpers";
import { groupPoliciesByResourceType } from "../policies/policyListHelpers";

interface StatusSectionProps {
    heading: string;
    isLoading: boolean;
    isError: boolean;
    loadingMessage: string;
    failedMessage: string;
    children: React.ReactNode;
}

/** One policies/permissions block below, each with its own independent
 * loading/error/content state. Unlike UserDetailsDialog's
 * AuthorizationSection, there's no "restricted" state here: every query
 * this card fires is the self-service /me variant (auth-only, no extra
 * permission needed), so isError only ever means a genuine failure, never
 * a permission gap. */
const StatusSection: React.FC<StatusSectionProps> = ({ heading, isLoading, isError, loadingMessage, failedMessage, children }) => (
    <div className="flex flex-col gap-2">
        <SectionHeading>{heading}</SectionHeading>
        {isLoading ? (
            <LoadingState message={loadingMessage} />
        ) : isError ? (
            <FormAlert size="lg" status="error">{failedMessage}</FormAlert>
        ) : (
            children
        )}
    </div>
);

/**
 * AccountStatusCard
 * ----------------------------
 * Read-only view of the caller's own full authorization picture: assigned
 * policies, effective permissions (the fanned-out union of every policy's
 * actions and direct grants, via the same buildEffectivePermissionList
 * UserDetailsDialog's permission-management "View" panel uses), and direct grants
 * specifically. Password status/change lives on its own Password tab
 * instead, since it isn't part of authorization. All three sections come
 * from the self-service /me endpoints (auth-only, no extra permission
 * needed), so this works for any authenticated user, not just users with management permissions who
 * can open UserDetailsDialog on the Users page.
 *
 * Both permission lists run through dedupeAgainstWildcards before
 * rendering: a grant of some action on a specific resource_type is already
 * covered by that same action on "*", so showing both as separate badges
 * would read as duplication.
 *
 * All sections share one card with dividers rather than separate cards, to
 * avoid extra padding/heading overhead for no real separation of concerns.
 *
 * Laid out as a 2-column grid on md+ (My policies and Direct permissions,
 * the things actually assigned to me, on the left; the computed Effective
 * permissions union on the right) rather than one stacked column: badge-heavy
 * permission lists often run a dozen-plus entries, and stacking them
 * vertically pushed this tab past a normal laptop viewport. Single column
 * below `md`, where two columns would each be too narrow for a badge to read
 * comfortably.
 *
 * Columns are split `fit-content(320px) 1fr`, not evenly: My policies/Direct
 * permissions are typically a handful of entries capped at 320px, while
 * Effective permissions on the right is usually the longest list and gets
 * the rest of the width, which matters more now that this tab runs the full
 * page width (see AccountSettingsPage.tsx).
 */
const AccountStatusCard: React.FC = () => {
    const { t } = useTranslation("account_settings");
    const { data: myPolicies, isLoading: policiesLoading, isError: policiesError } = useMyPoliciesQuery();
    const { data: myPermissions, isLoading: permissionsLoading, isError: permissionsError } = useMyPermissionsQuery();

    const policies = myPolicies?.policies ?? [];
    const rawDirectPermissions = myPermissions?.permissions ?? [];
    // Only accurate once both queries resolve: a partial union would
    // understate what the caller can really do (same guard as
    // UserDetailsDialog's canReadEffectivePermissions).
    const bothLoaded = !policiesLoading && !policiesError && !permissionsLoading && !permissionsError;
    // Carries policy-name/"Direct" source labels, same as UserDetailsDialog's
    // permission-management equivalent, so AccessResourceCards can show WHY the
    // caller holds each grant, not just what they hold.
    const effectiveWithSource = bothLoaded
        ? dedupeAgainstWildcards(buildEffectiveGrantsWithSource(policies, rawDirectPermissions))
        : [];
    const effectivePermissions = effectiveWithSource.map((g) => ({
        action: g.action,
        resource_type: g.resource_type,
        sourceLabels: g.direct ? [...g.policyNames, t("accountStatus.directSourceLabel")] : g.policyNames,
    }));
    // Dedupe raw direct grants against the full effective set (policies +
    // direct grants), not just against each other: a policy's own wildcard
    // (e.g. "system_superuser" on resource_type "*") already covers a direct
    // grant on a specific resource_type. Falls back to deduping against
    // itself while policies haven't loaded yet.
    const directPermissions = dedupeAgainstWildcards(
        rawDirectPermissions,
        bothLoaded ? effectiveWithSource : rawDirectPermissions
    );

    return (
        <Card className="p-5">
            {/* alignItems="start": Grid's default (stretch) would force both
                columns to the height of the taller one, usually the right column,
                leaving the shorter column with a trailing gap of whitespace
                instead of ending where its content ends. Same as
                UserDetailsDialog's Grid. */}
            <div className="grid grid-cols-1 md:grid-cols-[fit-content(320px)_1fr] gap-0 items-start">
                <div className="flex flex-col gap-4 min-w-0 pb-4 md:pb-0 md:pe-6">
                    <StatusSection
                        heading={t("accountStatus.myPolicies")}
                        isLoading={policiesLoading}
                        isError={policiesError}
                        loadingMessage={t("accountStatus.loadingPolicies")}
                        failedMessage={t("accountStatus.failedLoadPolicies")}
                    >
                        {policies.length > 0 ? (
                            <div className="flex flex-col gap-3">
                                {groupPoliciesByResourceType(policies).map(([resourceType, groupedPolicies]) => (
                                    <div key={resourceType} className="flex flex-col gap-1.5">
                                        <span className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
                                            {formatResourceTypeLabel(resourceType)}
                                        </span>
                                        {groupedPolicies.map((p) => (
                                            <p key={p.name} className="text-sm font-medium text-fg-default">
                                                {p.name}
                                            </p>
                                        ))}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-fg-muted">{t("accountStatus.noPolicies")}</p>
                        )}
                    </StatusSection>

                    <div className="border-t border-border-default" />

                    {/* Raw direct grants only, not fanned out through any policy,
                        so it's clear which entries in Effective permissions came
                        from a one-off grant versus an assigned policy. Placed under
                        My policies since both are "what was assigned to me", while
                        Effective permissions on the right is the computed union of
                        both. */}
                    <StatusSection
                        heading={t("accountStatus.directPermissions")}
                        isLoading={permissionsLoading}
                        isError={permissionsError}
                        loadingMessage={t("accountStatus.loadingDirectPermissions")}
                        failedMessage={t("accountStatus.failedLoadDirectPermissions")}
                    >
                        <AccessResourceCards items={directPermissions} emptyText={t("accountStatus.noDirectPermissions")} />
                    </StatusSection>
                </div>

                <div className="flex flex-col gap-4 min-w-0 pt-4 md:pt-0 md:ps-6 border-t md:border-t-0 md:border-s border-border-default">
                    {/* Union of every action the caller holds either way (policies
                        and direct grants), not just the raw direct grants in the
                        left column, so this reads as "everything I can actually do".
                        Same shape as UserDetailsDialog's permission-management equivalent. */}
                    <StatusSection
                        heading={t("accountStatus.effectivePermissions")}
                        isLoading={policiesLoading || permissionsLoading}
                        isError={policiesError || permissionsError}
                        loadingMessage={t("accountStatus.loadingEffectivePermissions")}
                        failedMessage={t("accountStatus.failedLoadEffectivePermissions")}
                    >
                        <AccessResourceCards items={effectivePermissions} emptyText={t("accountStatus.noPermissions")} />
                    </StatusSection>
                </div>
            </div>
        </Card>
    );
};

export default AccountStatusCard;
