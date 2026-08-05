import React from "react";
import { SimpleGrid } from "@chakra-ui/react";

import Card from "../ui/Card";
import StatTile from "../ui/StatTile";
import type { PolicyRead } from "../api/policies_api";

interface PolicyStatsCardProps {
    policies: PolicyRead[] | undefined;
    isLoading: boolean;
}

/**
 * PolicyStatsCard
 * ----------------------------
 * Summary counts for PoliciesPage, derived client-side from the already-
 * fully-loaded policy list (GET /authorization/policies loads everything at
 * once - see PoliciesPage's own comment on why - so there's no separate
 * aggregate endpoint to call here, unlike UserStatsCard's server-paginated
 * equivalent): total policies, how many are active, how many distinct
 * actions/permissions are granted across all of them, and how many distinct
 * resource types ("policy groups") those policies are organized under. Sits
 * between PageContainer's title and the Create Policy button, in the same
 * header row.
 */
const PolicyStatsCard: React.FC<PolicyStatsCardProps> = ({ policies, isLoading }) => {
    const totalPolicies = policies?.length;
    const activePolicies = policies?.filter((p) => p.is_active).length;
    const totalActions = policies ? new Set(policies.flatMap((p) => p.actions)).size : undefined;
    const resourceTypes = policies ? new Set(policies.map((p) => p.resource_type)).size : undefined;

    return (
        <Card p={4} w={{ base: "full", md: "280px" }}>
            <SimpleGrid columns={2} gap={4}>
                <StatTile label="Total policies" value={totalPolicies} isLoading={isLoading} color="blue.500" />
                <StatTile label="Active" value={activePolicies} isLoading={isLoading} color="green.500" />
                <StatTile label="Distinct actions" value={totalActions} isLoading={isLoading} color="purple.500" />
                <StatTile label="Resource types" value={resourceTypes} isLoading={isLoading} color="orange.500" />
            </SimpleGrid>
        </Card>
    );
};

export default PolicyStatsCard;
