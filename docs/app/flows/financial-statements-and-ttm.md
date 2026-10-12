# Financial Statements and TTM Flow
---

Income and cash-flow statements use a curated set of provider fields and an
explicit annual or quarterly period key. This page shows how an import becomes
deterministic annual and trailing-twelve-month metrics.
---

## Import and calculation

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Request["Import statement period"] --> Auth["Check company import permission"]
    Auth --> Period{"Annual or quarter 1-4?"}
    Period -->|invalid| Reject["400 invalid period"]
    Period -->|valid| Provider["Fetch income or cash-flow data"]
    Provider --> Rows{"Provider row available?"}
    Rows -->|no| Empty["Record no-data attempt"]
    Rows -->|yes| Existing{"Period already stored?"}
    Existing -->|no| Persist["Persist curated values and provenance"]
    Existing -->|refresh| Snapshot["Snapshot previous version"]
    Snapshot --> Persist
    Persist --> Analyze["Calculate annual metrics"]
    Analyze --> Four{"Four consecutive quarters?"}
    Four -->|yes| TTM["Calculate TTM aggregates"]
    Four -->|no| Annual["Return available annual metrics"]
    TTM --> Result["Return margins, cash conversion, warnings"]
    Annual --> Result
    Provider -->|fetch failure| Failed["Record failure; return 502"]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Persist,Analyze,TTM,Annual,Result success
    class Reject,Empty,Failed blocked
    class Period,Rows,Existing,Four decision
```
---

## Period rules

---

- Annual periods use `period_type=annual` and `period_number=0`.
- Quarterly periods use `period_type=quarterly` and a quarter number from 1 to 4.
- TTM values are produced only when four complete consecutive quarters are
  available. The analysis does not fill gaps or infer missing quarters.
- Refresh preserves the previous row in a snapshot and increments its version.
---

## Code references

---

- `backend/app/api/financial_statement_routes/financial_statement_routes.py`
- `backend/app/financial_statements/financial_statement_crud.py`
- `backend/app/financial_statements/statement_analysis.py`
- `backend/app/procrastinate_tasks/financial_refresh_tasks.py`
- `frontend/src/app/financial-statements/FinancialStatementsPanel.tsx`
---

## See also

---

- [App API reference](../api.md#income-and-cash-flow-statements)
- [Balance-sheet import and analysis](balance-sheet-import-and-analysis.md)
- [Feature implementation notes](../features.md)
