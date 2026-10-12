import React from "react";
import type { TFunction } from "i18next";
import { Button, Card, FormAlert, Input } from "../sdk";
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
        <Card className="mb-6 p-5">
            <form onSubmit={onSubmit}>
                <div className="flex flex-col gap-3">
                    <p className="text-sm text-fg-muted">
                        {isLookingUpTicker ? t("tickerLookupInProgress") : t("tickerLookupHint")}
                    </p>
                    <div className="relative">
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
                            <Card className="absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto p-1">
                                {tickerSuggestions.map((result) => (
                                    <button
                                        type="button"
                                        key={result.ticker}
                                        className="w-full rounded-md px-3 py-2 text-left hover:bg-bg-muted"
                                        onClick={() => selectTickerSuggestion(result)}
                                    >
                                        <span className="block text-sm font-medium">
                                            {result.ticker}
                                            {result.exchange ? ` · ${result.exchange}` : ""}
                                        </span>
                                        <span className="block text-xs text-fg-muted">
                                            {result.name}
                                        </span>
                                    </button>
                                ))}
                            </Card>
                        )}
                    </div>
                    {duplicateTickerCompany && (
                        <p className="text-sm text-red-400">
                            {t("duplicateTickerWarning", {
                                ticker: duplicateTickerCompany.ticker,
                                name: duplicateTickerCompany.name,
                            })}
                        </p>
                    )}
                    <Input placeholder={t("namePlaceholder")} value={name} onChange={(e) => setName(e.target.value)} required />
                    <Input
                        placeholder={t("parentCompanyIdPlaceholder")}
                        value={parentCompanyId}
                        onChange={(e) => setParentCompanyId(e.target.value)}
                        type="number"
                    />
                    {formMutation.isError && <FormAlert status="error">{formErrorMessage}</FormAlert>}
                    <div className="flex flex-wrap gap-2">
                        <Button
                            type="submit"
                            variant="brand"
                            loading={formMutation.isPending}
                            disabled={Boolean(duplicateTickerCompany)}
                        >
                            {editingCompany ? t("saveChanges") : t("create")}
                        </Button>
                        {editingCompany && (
                            <Button type="button" variant="outline" onClick={onCancel}>
                                {t("cancel")}
                            </Button>
                        )}
                    </div>
                </div>
            </form>
        </Card>
    );
};

export default CompanyFormCard;
