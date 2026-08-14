import React from "react";
import { Box, Button, Input, Stack, Text } from "@chakra-ui/react";
import type { TFunction } from "i18next";
import { Card, FormAlert } from "../sdk";
import { BRAND_SOLID_HOVER_PROPS } from "../app_sdk";
import type { CompanyListItem } from "../api/company_api";
import type { useTickerAutofill } from "./useTickerAutofill";

type TickerAutofill = ReturnType<typeof useTickerAutofill>;

interface CompanyFormCardProps {
    t: TFunction;
    editingCompany: CompanyListItem | null;
    name: string;
    setName: (name: string) => void;
    parentCompanyId: string;
    setParentCompanyId: (id: string) => void;
    tickerAutofill: TickerAutofill;
    formMutation: { isError: boolean; isPending: boolean };
    formErrorMessage: string | undefined;
    onSubmit: (e: React.SubmitEvent<HTMLFormElement>) => void;
    onCancel: () => void;
}

/**
 * The create/edit form Card, including the ticker-suggestion dropdown.
 * Purely presentational: all ticker-lookup state/behavior lives in useTickerAutofill.
 */
const CompanyFormCard: React.FC<CompanyFormCardProps> = ({
    t,
    editingCompany,
    name,
    setName,
    parentCompanyId,
    setParentCompanyId,
    tickerAutofill,
    formMutation,
    formErrorMessage,
    onSubmit,
    onCancel,
}) => {
    const {
        ticker,
        setTicker,
        isLookingUpTicker,
        showTickerSuggestions,
        setShowTickerSuggestions,
        tickerSuggestions,
        duplicateTickerCompany,
        selectTickerSuggestion,
        handleTickerFieldBlur,
        handleTickerFieldFocus,
    } = tickerAutofill;

    return (
        <Card p={5} mb={6}>
            <form onSubmit={onSubmit}>
                <Stack gap={3}>
                    <Text color="fg.muted" fontSize="sm">
                        {isLookingUpTicker ? t("tickerLookupInProgress") : t("tickerLookupHint")}
                    </Text>
                    <Box position="relative">
                        <Input
                            placeholder={t("tickerPlaceholder")}
                            value={ticker}
                            onChange={(e) => {
                                setTicker(e.target.value);
                                setShowTickerSuggestions(true);
                            }}
                            onFocus={handleTickerFieldFocus}
                            onBlur={handleTickerFieldBlur}
                            required
                        />
                        {showTickerSuggestions && tickerSuggestions.length > 0 && (
                            <Card position="absolute" top="100%" left={0} right={0} mt={1} p={1} zIndex={10} maxH="240px" overflowY="auto">
                                {tickerSuggestions.map((result) => (
                                    <Box
                                        key={result.ticker}
                                        px={3}
                                        py={2}
                                        borderRadius="md"
                                        cursor="pointer"
                                        _hover={{ bg: "bg.muted" }}
                                        onClick={() => selectTickerSuggestion(result)}
                                    >
                                        <Text fontSize="sm" fontWeight="medium">
                                            {result.ticker}
                                            {result.exchange ? ` · ${result.exchange}` : ""}
                                        </Text>
                                        <Text fontSize="xs" color="fg.muted">
                                            {result.name}
                                        </Text>
                                    </Box>
                                ))}
                            </Card>
                        )}
                    </Box>
                    {duplicateTickerCompany && (
                        <Text color="red.500" fontSize="sm">
                            {t("duplicateTickerWarning", {
                                ticker: duplicateTickerCompany.ticker,
                                name: duplicateTickerCompany.name,
                            })}
                        </Text>
                    )}
                    <Input placeholder={t("namePlaceholder")} value={name} onChange={(e) => setName(e.target.value)} required />
                    <Input
                        placeholder={t("parentCompanyIdPlaceholder")}
                        value={parentCompanyId}
                        onChange={(e) => setParentCompanyId(e.target.value)}
                        type="number"
                    />
                    {formMutation.isError && <FormAlert status="error">{formErrorMessage}</FormAlert>}
                    <Stack direction="row" gap={2}>
                        <Button
                            type="submit"
                            colorPalette="brand"
                            alignSelf="flex-start"
                            loading={formMutation.isPending}
                            disabled={Boolean(duplicateTickerCompany)}
                            {...BRAND_SOLID_HOVER_PROPS}
                        >
                            {editingCompany ? t("saveChanges") : t("create")}
                        </Button>
                        {editingCompany && (
                            <Button type="button" variant="outline" alignSelf="flex-start" onClick={onCancel}>
                                {t("cancel")}
                            </Button>
                        )}
                    </Stack>
                </Stack>
            </form>
        </Card>
    );
};

export default CompanyFormCard;
