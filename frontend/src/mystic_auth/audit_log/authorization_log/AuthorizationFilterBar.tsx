import React from "react";
import { HStack } from "@chakra-ui/react";

import StyledSelect from "../../ui/StyledSelect";
import { PERMISSIONS } from "../../authorization/permissions";
import { AUTHORIZATION_RESOURCE_TYPES } from "./resourceTypes";
import { ALL_VALUE } from "../auditLogListConfig";

interface AuthorizationFilterBarProps {
    action: string;
    setAction: (v: string) => void;
    resourceType: string;
    setResourceType: (v: string) => void;
    allowed: string;
    setAllowed: (v: string) => void;
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
}) => (
    <HStack gap={3} mb={4} wrap="wrap">
        <StyledSelect
            w="220px"
            ariaLabel="Filter by action"
            value={action}
            onChange={setAction}
            options={[
                { value: ALL_VALUE, label: "All actions" },
                ...Object.values(PERMISSIONS).map((value) => ({ value, label: value })),
            ]}
        />

        <StyledSelect
            w="160px"
            ariaLabel="Filter by resource type"
            value={resourceType}
            onChange={setResourceType}
            options={[
                { value: ALL_VALUE, label: "All resources" },
                ...AUTHORIZATION_RESOURCE_TYPES.map((value) => ({ value, label: value })),
            ]}
        />

        <StyledSelect
            w="140px"
            ariaLabel="Filter by result"
            value={allowed}
            onChange={setAllowed}
            options={[
                { value: ALL_VALUE, label: "All results" },
                { value: "true", label: "Allowed" },
                { value: "false", label: "Denied" },
            ]}
        />
    </HStack>
);

export default AuthorizationFilterBar;
