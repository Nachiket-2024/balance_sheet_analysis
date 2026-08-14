import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";

import { toaster } from "../sdk";
import { useDebouncedValue } from "../app_sdk";
import { useTickerSearchQuery } from "./companyQueries";
import { lookupCompanyTickerApi, listCompaniesApi, type CompanyListItem } from "../api/company_api";

// Shorter searches have a near-100% match rate, so skip unhelpful requests.
const MIN_TICKER_SEARCH_LENGTH = 2;

const extractErrorDetail = (error: unknown, fallback: string): string =>
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

/**
 * Ticker-driven bits of the company form: suggestion dropdown, best-effort
 * name autofill on blur, and the narrow duplicate-ticker warning. Pulled out
 * of CompaniesPage so that page only owns page-level state (search/sort/pagination).
 */
export function useTickerAutofill(showForm: boolean, name: string, setName: (name: string) => void, editingCompanyId: number | undefined, t: TFunction) {
    const [ticker, setTicker] = useState("");
    const [isLookingUpTicker, setIsLookingUpTicker] = useState(false);
    const [showTickerSuggestions, setShowTickerSuggestions] = useState(false);
    // Delays hiding the dropdown past a suggestion's own onClick, since a
    // plain onBlur fires first and would otherwise unmount the option before
    // the click on it is ever registered.
    const suggestionsBlurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

    const trimmedTicker = ticker.trim();
    const debouncedTicker = useDebouncedValue(trimmedTicker, 300);
    const tickerSearchQuery = useTickerSearchQuery(debouncedTicker, {
        enabled: showForm && showTickerSuggestions && debouncedTicker.length >= MIN_TICKER_SEARCH_LENGTH,
    });
    const tickerSuggestions =
        debouncedTicker === trimmedTicker && debouncedTicker.length >= MIN_TICKER_SEARCH_LENGTH
            ? (tickerSearchQuery.data?.results ?? [])
            : [];

    // Narrow server-side duplicate check. The DB unique constraint is still
    // the source of truth at submit time.
    const duplicateCheckQuery = useQuery({
        queryKey: ["companies", "duplicate-ticker-check", debouncedTicker],
        queryFn: async () => (await listCompaniesApi({ search: debouncedTicker, limit: 5 })).data,
        enabled: showForm && debouncedTicker.length > 0,
    });
    const duplicateTickerCompany = duplicateCheckQuery.data?.find(
        (c: CompanyListItem) => c.ticker.toLowerCase() === debouncedTicker.toLowerCase() && c.id !== editingCompanyId
    );

    const reset = () => {
        setTicker("");
        setShowTickerSuggestions(false);
    };

    const selectTickerSuggestion = (result: { ticker: string; name: string }) => {
        setTicker(result.ticker);
        setName(result.name);
        setShowTickerSuggestions(false);
    };

    // Best-effort autofill only when the name field is still blank.
    const handleTickerBlur = async () => {
        const trimmed = ticker.trim();
        if (!trimmed || name.trim()) return;

        setIsLookingUpTicker(true);
        try {
            const { data } = await lookupCompanyTickerApi(trimmed);
            if (data.name) {
                setName(data.name);
            } else {
                toaster.create({ title: t("noTickerFound", { ticker: trimmed }), type: "info" });
            }
        } catch (error) {
            toaster.create({
                title: extractErrorDetail(error, t("tickerLookupFailed")),
                type: "error",
            });
        } finally {
            setIsLookingUpTicker(false);
        }
    };

    const handleTickerFieldBlur = () => {
        // Give a suggestion's onClick a chance to fire first (see the ref's
        // own comment above), then run the existing autofill lookup as before.
        suggestionsBlurTimeout.current = setTimeout(() => setShowTickerSuggestions(false), 150);
        void handleTickerBlur();
    };

    const handleTickerFieldFocus = () => {
        if (suggestionsBlurTimeout.current) clearTimeout(suggestionsBlurTimeout.current);
        setShowTickerSuggestions(true);
    };

    return {
        ticker,
        setTicker,
        isLookingUpTicker,
        showTickerSuggestions,
        setShowTickerSuggestions,
        tickerSuggestions,
        duplicateTickerCompany,
        reset,
        selectTickerSuggestion,
        handleTickerFieldBlur,
        handleTickerFieldFocus,
    };
}
