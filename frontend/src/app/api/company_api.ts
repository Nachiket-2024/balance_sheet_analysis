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

export interface CompanyCreatePayload {
    name: string;
    ticker: string;
    parent_company_id?: number | null;
}

// Trailing slash matters here: FastAPI's router prefix is "/companies"
// with routes at "/" and "/{id}", so "/companies" (no slash) 307-redirects
// to "/companies/", which axios only follows for GET, not POST bodies.
export const listCompaniesApi = () => api.get<Company[]>("/companies/");

export const getCompanyApi = (companyId: number) => api.get<Company>(`/companies/${companyId}`);

export const createCompanyApi = (payload: CompanyCreatePayload) => api.post<Company>("/companies/", payload);

export const deleteCompanyApi = (companyId: number) => api.delete(`/companies/${companyId}`);
