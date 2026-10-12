# Saved Management Review Flow
---

A saved review is a point-in-time snapshot of deterministic analysis and the
fiscal years included. Later imports do not rewrite the saved analysis.
---

## Review lifecycle

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    User["Authorized user selects company and years"] --> Rows["Load selected balance-sheet periods"]
    Rows --> Empty{"Any period found?"}
    Empty -->|no| Reject["400 period required"]
    Empty -->|yes| Analyze["Calculate deterministic analysis"]
    Analyze --> Save["Create draft with years and analysis snapshot"]
    Save --> Work["Add comments or reviewer assignments"]
    Work --> Review["Set report status to reviewed"]
    Review --> Approve["Set report status to approved"]
    Approve --> Supersede["Optionally set status to superseded"]
    Review --> Signoff["Optionally record a sign-off with a status and note"]
    Approve --> Signoff
    Supersede --> Export["Export escaped HTML report"]
    Signoff --> Export
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Save,Work,Review,Approve,Supersede,Signoff,Export success
    class Reject blocked
    class Empty,Signoff decision
```
---

## Scope and retained state

---

Every report, comment, assignment, and sign-off is authorized through the
report's company. The accepted report statuses are `draft`, `reviewed`,
`approved`, and `superseded`; status changes are not restricted to a fixed
transition graph. Sign-offs are separate history records and also set the
report status to the submitted value. HTML export escapes report content and
carries the screening disclaimer. The snapshot stores deterministic values
and the years used; it does not claim to be accounting, tax, legal, or
investment advice.
---

## Code references

---

- `backend/app/api/review_routes/review_routes.py`
- `backend/app/reviews/review_model.py`
- `backend/app/reviews/review_schema.py`
- `frontend/src/app/reviews/ReviewReportPanel.tsx`
---

## See also

---

- [App API reference](../api.md#saved-reviews)
- [Balance-sheet import and analysis](balance-sheet-import-and-analysis.md)
