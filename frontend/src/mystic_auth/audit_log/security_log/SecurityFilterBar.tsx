import React from "react";
import { HStack, Input } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import StyledSelect from "../../ui/StyledSelect";
import { SEARCH_INPUT_PROPS } from "../../ui/styles/inputStyles";
import { SECURITY_EVENT_TYPES } from "./securityLogEventTypes";
import { ALL_VALUE } from "../auditLogListConfig";

interface SecurityFilterBarProps {
    eventType: string;
    setEventType: (v: string) => void;
    ipAddress: string;
    setIpAddress: (v: string) => void;
    success: string;
    setSuccess: (v: string) => void;
}

const SecurityFilterBar: React.FC<SecurityFilterBarProps> = ({
    eventType, setEventType, ipAddress, setIpAddress, success, setSuccess,
}) => {
    const { t } = useTranslation("audit_log");

    return (
        <HStack gap={3} mb={4} wrap="wrap">
            <StyledSelect
                w="220px"
                ariaLabel={t("security.filterBar.filterByEvent")}
                value={eventType}
                onChange={setEventType}
                options={[
                    { value: ALL_VALUE, label: t("security.filterBar.allEvents") },
                    ...SECURITY_EVENT_TYPES.map((value) => ({ value, label: value })),
                ]}
            />

            <Input
                placeholder={t("security.filterBar.filterByIpPlaceholder")}
                aria-label={t("security.filterBar.filterByIpAddress")}
                value={ipAddress}
                onChange={(e) => setIpAddress(e.target.value)}
                w="160px"
                {...SEARCH_INPUT_PROPS}
            />

            <StyledSelect
                w="140px"
                ariaLabel={t("security.filterBar.filterByResult")}
                value={success}
                onChange={setSuccess}
                options={[
                    { value: ALL_VALUE, label: t("security.filterBar.allResults") },
                    { value: "true", label: t("security.results.success") },
                    { value: "false", label: t("security.results.failed") },
                ]}
            />
        </HStack>
    );
};

export default SecurityFilterBar;
