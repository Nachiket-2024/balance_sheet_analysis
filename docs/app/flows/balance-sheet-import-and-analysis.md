# Balance-Sheet Import and Analysis Flow
---

This flow covers a company's annual balance-sheet import, refresh history,
scoped analysis, and optional currency normalization.
---

## Import and analysis

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    User["Analyst requests fiscal year"] --> Auth["Authenticate and check balance_sheet:import"]
    Auth --> Fetch["Fetch yfinance data with timeout"]
    Fetch --> HasData{"Data available?"}
    HasData -->|no| NoData["400 no data"]
    HasData -->|yes| Existing{"Existing period?"}
    Existing -->|no| Save["Save values and provenance"]
    Existing -->|yes, refresh false| Conflict["400 duplicate period"]
    Existing -->|yes, refresh true| Snapshot["Snapshot current version"]
    Snapshot --> Save
    Save --> Analysis["Calculate deterministic metrics and warnings"]
    Analysis --> Normalize{"Target currency requested?"}
    Normalize -->|no| Response["Return reported-currency analysis"]
    Normalize -->|yes| Rates["Apply dated company conversion rates"]
    Rates --> Response
    Fetch -->|provider or network failure| Failed["502 provider failure; retain attempt"]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Save,Analysis,Response success
    class NoData,Conflict,Failed blocked
    class HasData,Existing,Normalize decision
```
---

## Data retained

---

Each period stores provider provenance, source fields, period end date,
currency and scale when known, quality status, and a version. Refresh saves the
previous values into `balance_sheet_snapshots` before replacing the current
period. Failed, empty, duplicate, and successful import attempts remain
available as operational history.

Analysis uses the persisted rows. Missing values and non-positive ratio
denominators remain explicitly unavailable. Conversion uses dated,
company-owned rates; the response identifies the rate source and periods that
could not be converted.
---

## Code references

---

- `backend/app/api/balance_sheet_routes/balance_sheet_routes.py`
- `backend/app/balance_sheets/balance_sheet_crud.py`
- `backend/app/api/analysis_routes/analysis_routes.py`
- `backend/app/balance_sheets/analysis_service.py`
- `backend/app/balance_sheets/currency_service.py`
- `frontend/src/app/companies/CompanyDetailPage.tsx`
---

## See also

---

- [App API reference](../api.md#balance-sheets)
- [Feature implementation notes](../features.md#balance-sheet-provenance-and-refreshes)
- [Financial statements and TTM](financial-statements-and-ttm.md)
