import React, { useRef, useState } from "react";
import { Box, Button, HStack, Input, Stack, Text } from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { PageContainer, DataTable, type DataTableColumn, Card, ConfirmDialog, FormAlert, toaster, IfCan } from "../sdk";
import {
    TableActionButton,
    BRAND_SOLID_HOVER_PROPS,
    BRAND_OUTLINE_HOVER_PROPS,
    StyledSelect,
    SEARCH_INPUT_PROPS,
    useSortState,
    useDebouncedValue,
    Pagination,
    usePageResetOn,
} from "../app_sdk";
import { APP_PERMISSIONS } from "../access/permissions";
import {
    useCompaniesQuery,
    useCreateCompanyMutation,
    useDeleteCompanyMutation,
    useTickerSearchQuery,
    useUpdateCompanyMutation,
} from "./companyQueries";
import CompanyStatsCard from "./CompanyStatsCard";
import { lookupCompanyTickerApi, listCompaniesApi, type CompanyListItem } from "../api/company_api";

// Shorter searches have a near-100% match rate, so skip unhelpful requests.
const MIN_TICKER_SEARCH_LENGTH = 2;

const PAGE_SIZE = 25;
const ALL_VALUE = "";

const extractErrorDetail = (error: unknown, fallback: string): string =>
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

/**
 * Every company `current_user` may read. The backend scopes GET /companies/,
 * so this page never needs a client-side permission filter per row.
 *
 * Search/hierarchy-filter/sort all run server-side (see companyQueries.ts),
 * since an admin-scoped user can see an unbounded company list.
 */
const CompaniesPage: React.FC = () => {
    const navigate = useNavigate();
    const createMutation = useCreateCompanyMutation();
    const updateMutation = useUpdateCompanyMutation();
    const deleteMutation = useDeleteCompanyMutation();

    const [showForm, setShowForm] = useState(false);
    const [editingCompany, setEditingCompany] = useState<CompanyListItem | null>(null);
    const [name, setName] = useState("");
    const [ticker, setTicker] = useState("");
    const [parentCompanyId, setParentCompanyId] = useState("");
    const [deletingCompany, setDeletingCompany] = useState<CompanyListItem | null>(null);
    const [isLookingUpTicker, setIsLookingUpTicker] = useState(false);
    const [showTickerSuggestions, setShowTickerSuggestions] = useState(false);
    // Delays hiding the dropdown past a suggestion's own onClick, since a
    // plain onBlur fires first and would otherwise unmount the option before
    // the click on it is ever registered.
    const suggestionsBlurTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

    const [search, setSearch] = useState("");
    // Debounce server-side search so typing does not fire per-character requests.
    const debouncedSearch = useDebouncedValue(search);
    const [hierarchy, setHierarchy] = useState(ALL_VALUE);
    const { sort, toggleSort } = useSortState("");

    // Search/filter/sort changes can invalidate the current page number.
    const [page, setPage] = usePageResetOn(`${debouncedSearch}|${sort.key}|${sort.direction}|${hierarchy}`);

    const { data, isLoading, isError } = useCompaniesQuery(page, PAGE_SIZE, {
        search: debouncedSearch,
        hierarchy: (hierarchy || undefined) as "root" | "subsidiary" | undefined,
        sortBy: sort.key || undefined,
        sortDir: sort.direction,
    });
    const companies = data?.companies;
    const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

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
        (c) => c.ticker.toLowerCase() === debouncedTicker.toLowerCase() && c.id !== editingCompany?.id
    );

    const closeForm = () => {
        setShowForm(false);
        setEditingCompany(null);
        setName("");
        setTicker("");
        setParentCompanyId("");
        setShowTickerSuggestions(false);
    };

    const openCreateForm = () => {
        setEditingCompany(null);
        setName("");
        setTicker("");
        setParentCompanyId("");
        setShowForm(true);
    };

    const openEditForm = (company: CompanyListItem) => {
        setEditingCompany(company);
        setName(company.name);
        setTicker(company.ticker);
        setParentCompanyId(company.parent_company_id != null ? String(company.parent_company_id) : "");
        setShowForm(true);
    };

    const selectTickerSuggestion = (result: { ticker: string; name: string }) => {
        setTicker(result.ticker);
        setName(result.name);
        setShowTickerSuggestions(false);
    };

    const handleTickerFieldBlur = () => {
        // Give a suggestion's onClick a chance to fire first (see the ref's
        // own comment above), then run the existing autofill lookup as before.
        suggestionsBlurTimeout.current = setTimeout(() => setShowTickerSuggestions(false), 150);
        void handleTickerBlur();
    };

    // Best-effort autofill only when the name field is still blank.
    const handleTickerBlur = async () => {
        const trimmedTicker = ticker.trim();
        if (!trimmedTicker || name.trim()) return;

        setIsLookingUpTicker(true);
        try {
            const { data } = await lookupCompanyTickerApi(trimmedTicker);
            if (data.name) {
                setName(data.name);
            } else {
                toaster.create({ title: `No company found for ticker '${trimmedTicker}'`, type: "info" });
            }
        } catch (error) {
            toaster.create({
                title: extractErrorDetail(error, "Couldn't look up that ticker, enter the company name manually"),
                type: "error",
            });
        } finally {
            setIsLookingUpTicker(false);
        }
    };

    const formMutation = editingCompany ? updateMutation : createMutation;

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        const payload = {
            name,
            ticker,
            parent_company_id: parentCompanyId ? Number(parentCompanyId) : null,
        };

        if (editingCompany) {
            updateMutation.mutate(
                { companyId: editingCompany.id, payload },
                {
                    onSuccess: () => {
                        toaster.create({ title: "Company updated", type: "success" });
                        closeForm();
                    },
                    onError: (error) =>
                        toaster.create({ title: extractErrorDetail(error, "Failed to update company"), type: "error" }),
                }
            );
            return;
        }

        createMutation.mutate(payload, {
            onSuccess: () => {
                toaster.create({ title: "Company created", type: "success" });
                closeForm();
            },
            onError: (error) => toaster.create({ title: extractErrorDetail(error, "Failed to create company"), type: "error" }),
        });
    };

    const handleDeleteConfirm = () => {
        if (deletingCompany === null) return;
        deleteMutation.mutate(deletingCompany.id, {
            onSuccess: () => {
                toaster.create({ title: `Deleted ${deletingCompany.name}`, type: "success" });
                setDeletingCompany(null);
            },
            onError: (error) => {
                toaster.create({ title: extractErrorDetail(error, "Failed to delete company"), type: "error" });
                setDeletingCompany(null);
            },
        });
    };

    const columns: DataTableColumn<CompanyListItem>[] = [
        { key: "name", header: "Name", sortable: true, render: (c) => c.name },
        { key: "ticker", header: "Ticker", sortable: true, render: (c) => c.ticker },
        {
            key: "parent",
            header: "Parent company",
            sortable: true,
            render: (c) => c.parent_name ?? "—",
        },
        {
            key: "row_actions",
            header: "",
            align: "end",
            render: (c) => (
                <Stack direction="row" gap={2} justify="flex-end">
                    <Button
                        size="xs"
                        variant="outline"
                        borderColor="brand.fg"
                        color="brand.fg"
                        onClick={() => navigate(`/companies/${c.id}`)}
                        {...BRAND_OUTLINE_HOVER_PROPS}
                    >
                        View
                    </Button>
                    <IfCan action={APP_PERMISSIONS.COMPANY_UPDATE}>
                        <TableActionButton onClick={() => openEditForm(c)}>Edit</TableActionButton>
                    </IfCan>
                    <IfCan action={APP_PERMISSIONS.COMPANY_DELETE}>
                        <TableActionButton colorPalette="red" onClick={() => setDeletingCompany(c)}>
                            Delete
                        </TableActionButton>
                    </IfCan>
                </Stack>
            ),
        },
    ];

    return (
        <PageContainer
            title="Companies"
            description="Companies and verticals you're assigned to review."
            actions={
                <CompanyStatsCard
                    onFilterTotal={() => {
                        setSearch("");
                        setHierarchy(ALL_VALUE);
                    }}
                    onFilterGroupRoots={() => {
                        setSearch("");
                        setHierarchy("root");
                    }}
                    onFilterSubsidiaries={() => {
                        setSearch("");
                        setHierarchy("subsidiary");
                    }}
                />
            }
            headerExtra={
                <HStack gap={3} wrap="wrap">
                    <Input
                        placeholder="Search by name or ticker..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        maxW="sm"
                        {...SEARCH_INPUT_PROPS}
                    />

                    <StyledSelect
                        w="160px"
                        ariaLabel="Filter by scope"
                        value={hierarchy}
                        onChange={setHierarchy}
                        options={[
                            { value: ALL_VALUE, label: "All companies" },
                            { value: "root", label: "Group roots" },
                            { value: "subsidiary", label: "Subsidiaries" },
                        ]}
                    />

                    <IfCan action={APP_PERMISSIONS.COMPANY_CREATE}>
                        <Button
                            size="sm"
                            colorPalette="brand"
                            onClick={() => (showForm ? closeForm() : openCreateForm())}
                            {...BRAND_SOLID_HOVER_PROPS}
                        >
                            {showForm ? "Cancel" : "Add company"}
                        </Button>
                    </IfCan>
                </HStack>
            }
        >
            {showForm && (
                <Card p={5} mb={6}>
                    <form onSubmit={handleSubmit}>
                        <Stack gap={3}>
                            <Text color="fg.muted" fontSize="sm">
                                {isLookingUpTicker
                                    ? "Looking up company name for that ticker…"
                                    : "Leave the name blank to autofill it from the ticker."}
                            </Text>
                            <Box position="relative">
                                <Input
                                    placeholder="Ticker (e.g. JIO.NS)"
                                    value={ticker}
                                    onChange={(e) => {
                                        setTicker(e.target.value);
                                        setShowTickerSuggestions(true);
                                    }}
                                    onFocus={() => {
                                        if (suggestionsBlurTimeout.current) clearTimeout(suggestionsBlurTimeout.current);
                                        setShowTickerSuggestions(true);
                                    }}
                                    onBlur={handleTickerFieldBlur}
                                    required
                                />
                                {showTickerSuggestions && tickerSuggestions.length > 0 && (
                                    <Card
                                        position="absolute"
                                        top="100%"
                                        left={0}
                                        right={0}
                                        mt={1}
                                        p={1}
                                        zIndex={10}
                                        maxH="240px"
                                        overflowY="auto"
                                    >
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
                                    A company with ticker '{duplicateTickerCompany.ticker}' already exists (
                                    {duplicateTickerCompany.name}).
                                </Text>
                            )}
                            <Input
                                placeholder="Company name (e.g. Jio Platforms)"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                            />
                            <Input
                                placeholder="Parent company ID (optional, leave blank for a group root)"
                                value={parentCompanyId}
                                onChange={(e) => setParentCompanyId(e.target.value)}
                                type="number"
                            />
                            {formMutation.isError && (
                                <FormAlert status="error">
                                    {extractErrorDetail(
                                        formMutation.error,
                                        editingCompany ? "Failed to update company" : "Failed to create company"
                                    )}
                                </FormAlert>
                            )}
                            <Stack direction="row" gap={2}>
                                <Button
                                    type="submit"
                                    colorPalette="brand"
                                    alignSelf="flex-start"
                                    loading={formMutation.isPending}
                                    disabled={Boolean(duplicateTickerCompany)}
                                    {...BRAND_SOLID_HOVER_PROPS}
                                >
                                    {editingCompany ? "Save changes" : "Create"}
                                </Button>
                                {editingCompany && (
                                    <Button type="button" variant="outline" alignSelf="flex-start" onClick={closeForm}>
                                        Cancel
                                    </Button>
                                )}
                            </Stack>
                        </Stack>
                    </form>
                </Card>
            )}

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mb={4} />

            <DataTable
                columns={columns}
                rows={companies}
                rowKey={(c) => c.id}
                isLoading={isLoading}
                isError={isError}
                errorMessage="Failed to load companies"
                emptyMessage={search || hierarchy ? "No companies match your search/filters" : "No companies assigned to you yet"}
                sort={sort}
                onSortChange={toggleSort}
                startIndex={(page - 1) * PAGE_SIZE}
            />

            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} mt={4} />

            {!isLoading && !isError && data?.total === 0 && (
                <Text color="fg.muted" mt={4} fontSize="sm">
                    You don't have access to any companies yet. Ask an administrator to assign you a policy.
                </Text>
            )}

            <ConfirmDialog
                isOpen={deletingCompany !== null}
                title="Delete company"
                description={`Delete ${deletingCompany?.name}? This also deletes every balance sheet on file for it. This cannot be undone.`}
                confirmLabel="Delete"
                isLoading={deleteMutation.isPending}
                onConfirm={handleDeleteConfirm}
                onCancel={() => setDeletingCompany(null)}
            />
        </PageContainer>
    );
};

export default CompaniesPage;
