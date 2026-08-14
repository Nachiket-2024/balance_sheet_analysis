import React from "react";
import { HStack } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import StyledSelect from "../../ui/StyledSelect";
import { PERMISSIONS } from "../../authorization/permissions";
import { AUTHORIZATION_RESOURCE_TYPES } from "./authorizationLogResourceTypes";
import { ALL_VALUE } from "../auditLogListConfig";

interface AuthorizationFilterBarProps {
    action: string;
    setAction: (v: string) => void;
    resourceType: string;
    setResourceType: (v: string) => void;
    allowed: string;
    setAllowed: (v: string) => void;
    /**
     * Resource types beyond this app's own AUTHORIZATION_RESOURCE_TYPES,
     * for downstream projects that extend the PBAC resource vocabulary
     * for their own business domain (see authorizationLogResourceTypes.ts's
     * docstring). Appended after the built-ins; omitting it renders the
     * dropdown exactly as before this prop existed.
     */
    extraResourceTypes?: string[];
    /** Same idea as extraResourceTypes, for actions beyond PERMISSIONS. */
    extraActions?: string[];
}

/**
 * Action/Resource/Result: a server-side filter (composes with search and
 * sort, narrows the whole result set, not just the loaded page), rendered
 * as selects rather than free text since all three are fixed, finite
 * vocabularies (PERMISSIONS' own action strings, this app's resource
 * types, and a bool) - typing them in would just invite typos that quietly
 * match nothing.
 */
const AuthorizationFilterBar: React.FC<AuthorizationFilterBarProps> = ({
    action, setAction, resourceType, setResourceType, allowed, setAllowed,
    extraResourceTypes, extraActions,
}) => {
    const { t } = useTranslation("audit_log");

    return (
        <HStack gap={3} mb={4} wrap="wrap">
            <StyledSelect
                w="220px"
                ariaLabel={t("authorization.filterBar.filterByAction")}
                value={action}
                onChange={setAction}
                options={[
                    { value: ALL_VALUE, label: t("authorization.filterBar.allActions") },
                    ...Object.values(PERMISSIONS).map((value) => ({ value, label: value })),
                    ...(extraActions ?? []).map((value) => ({ value, label: value })),
                ]}
            />

            <StyledSelect
                w="160px"
                ariaLabel={t("authorization.filterBar.filterByResourceType")}
                value={resourceType}
                onChange={setResourceType}
                options={[
                    { value: ALL_VALUE, label: t("authorization.filterBar.allResources") },
                    ...AUTHORIZATION_RESOURCE_TYPES.map((value) => ({ value, label: value })),
                    ...(extraResourceTypes ?? []).map((value) => ({ value, label: value })),
                ]}
            />

            <StyledSelect
                w="140px"
                ariaLabel={t("authorization.filterBar.filterByResult")}
                value={allowed}
                onChange={setAllowed}
                options={[
                    { value: ALL_VALUE, label: t("authorization.filterBar.allResults") },
                    { value: "true", label: t("authorization.results.allowed") },
                    { value: "false", label: t("authorization.results.denied") },
                ]}
            />
        </HStack>
    );
};

export default AuthorizationFilterBar;
