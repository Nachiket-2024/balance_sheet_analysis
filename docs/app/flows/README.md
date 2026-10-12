# Application Flows
---

This index links the request and background-job flows implemented by
`backend/app/` and `frontend/src/app/`. Each flow page has its own Mermaid
diagram and names the code that owns each step.

> Diagram omitted. See the surrounding prose, tables, or numbered steps for the same flow.
---

## Pages

---

- [Company access and onboarding](company-access-and-onboarding.md): create a
  company-scoped policy and serve authorized company data.
- [Balance-sheet import and analysis](balance-sheet-import-and-analysis.md):
  import or refresh a fiscal year, retain its history, and analyze it.
- [Financial statements and TTM](financial-statements-and-ttm.md): import
  annual or quarterly income and cash-flow data and calculate TTM metrics.
- [Grounded LLM chat](grounded-llm-chat.md): authorize a question, build a
  scoped financial context, enforce the budget, and record the result.
- [Saved management reviews](saved-management-reviews.md): persist a
  deterministic snapshot, review it, and export or sign it off.
- [Analysis alerts and delivery](analysis-alerts-and-delivery.md): persist
  warnings and deliver configured email or webhook notifications.
---

## See also

---

- [App API reference](../api.md)
- [Feature implementation notes](../features.md)
- [Company access control](../access-control/README.md)
- [Documentation index](../README.md)
