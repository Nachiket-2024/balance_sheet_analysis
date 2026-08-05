import React from "react";
import { HStack, Input } from "@chakra-ui/react";

import StyledSelect from "../../ui/StyledSelect";
import { SEARCH_INPUT_PROPS } from "../../ui/styles/inputStyles";
import { SECURITY_EVENT_TYPES } from "./eventTypes";
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
}) => (
    <HStack gap={3} mb={4} wrap="wrap">
        <StyledSelect
            w="220px"
            ariaLabel="Filter by event"
            value={eventType}
            onChange={setEventType}
            options={[
                { value: ALL_VALUE, label: "All events" },
                ...SECURITY_EVENT_TYPES.map((value) => ({ value, label: value })),
            ]}
        />

        <Input
            placeholder="Filter by IP..."
            aria-label="Filter by IP address"
            value={ipAddress}
            onChange={(e) => setIpAddress(e.target.value)}
            w="160px"
            {...SEARCH_INPUT_PROPS}
        />

        <StyledSelect
            w="140px"
            ariaLabel="Filter by result"
            value={success}
            onChange={setSuccess}
            options={[
                { value: ALL_VALUE, label: "All results" },
                { value: "true", label: "Success" },
                { value: "false", label: "Failed" },
            ]}
        />
    </HStack>
);

export default SecurityFilterBar;
