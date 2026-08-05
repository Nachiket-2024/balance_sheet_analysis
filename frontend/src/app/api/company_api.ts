import api from "@/api/axiosInstance";

export interface Company {
    id: number;
    name: string;
    ticker: string;
    parent_company_id: number | null;
    group_root_id: number;
    created_at: string;
    updated_at: string;
}

// GET /companies row shape. parent_name is resolved by the server-side join
// because CompaniesPage no longer has every scoped company loaded client-side.
export interface CompanyListItem extends Company {
    parent_name: string | null;
}

export interface CompanyStats {
    total: number;
    group_roots: number;
    subsidiaries: number;
}

export interface CompanyCreatePayload {
    name: string;
    ticker: string;
    parent_company_id?: number | null;
}

export interface CompanyUpdatePayload {
    name?: string;
    ticker?: string;
    parent_company_id?: number | null;
}

export interface TickerLookup {
    ticker: string;
    name: string | null;
}

export interface TickerSearchResult {
    ticker: string;
    name: string;
    exchange: string;
}

export interface TickerSearchResponse {
    query: string;
    results: TickerSearchResult[];
}

export interface ListCompaniesParams {
    limit?: number;
    offset?: number;
    /** Case-insensitive substring match on name or ticker. */
    search?: string;
    /** "root": companies with no parent. "subsidiary": companies with a
     * parent. Unset: both. */
    hierarchy?: "root" | "subsidiary";
    /** Column to sort by. Unsupported values are ignored server-side and fall back to id. */
    sortBy?: string;
    sortDir?: "asc" | "desc";
}

function toListCompaniesApiParams({ limit = 1000, offset = 0, search, hierarchy, sortBy, sortDir }: ListCompaniesParams) {
    return { limit, offset, search, hierarchy, sort_by: sortBy, sort_dir: sortDir };
}

// Trailing slash matters here: FastAPI's router prefix is "/companies"
// with routes at "/" and "/{id}", so "/companies" (no slash) 307-redirects
// to "/companies/", which axios only follows for GET, not POST bodies.
//
// X-Total-Count (total matching rows, ignoring limit/offset) rides the
// response headers rather than the body. companyQueries.ts derives page count
// from it, matching mystic_auth's listUsersApi convention.
export const listCompaniesApi = (params: ListCompaniesParams = {}) =>
    api.get<CompanyListItem[]>("/companies/", { params: toListCompaniesApiParams(params) });

// Aggregate counts (total/group roots/subsidiaries) across whatever this
// user is scoped to see, independent of the main list's current page/filters.
export const getCompanyStatsApi = () => api.get<CompanyStats>("/companies/stats");

export const getCompanyApi = (companyId: number) => api.get<Company>(`/companies/${companyId}`);

export const createCompanyApi = (payload: CompanyCreatePayload) => api.post<Company>("/companies/", payload);

export const updateCompanyApi = (companyId: number, payload: CompanyUpdatePayload) =>
    api.patch<Company>(`/companies/${companyId}`, payload);

export const deleteCompanyApi = (companyId: number) => api.delete(`/companies/${companyId}`);

// Best-effort autofill for the "add company" form: looks up a ticker's
// company name via the backend's yfinance-backed lookup. `name` comes back
// null (not a 404) for a ticker yfinance has nothing for.
export const lookupCompanyTickerApi = (ticker: string) =>
    api.get<TickerLookup>(`/companies/lookup/${encodeURIComponent(ticker)}`);

// Autocomplete for the "add company" form's ticker field: partial
// ticker/name -> candidate real-world matches, via the backend's
// yfinance-backed search (distinct from the exact-match lookup above).
export const searchCompanyTickersApi = (query: string) =>
    api.get<TickerSearchResponse>(`/companies/search/${encodeURIComponent(query)}`);
