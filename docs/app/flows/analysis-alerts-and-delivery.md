# Analysis Alerts and Delivery Flow
---

The analysis service emits warning evidence. The app reconciles those warnings
with durable company alerts, and a background worker queues eligible email and
optional webhook deliveries.
---

## Alert and notification flow

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Analysis["Calculate company analysis"] --> Warnings["Warnings with type, severity, evidence"]
    Warnings --> Reconcile["Create or update company alert rows"]
    Reconcile --> State["Keep first seen; update last seen"]
    State --> Worker["Background task selects open alerts"]
    Worker --> Policy{"Policy enabled and severity eligible?"}
    Policy -->|no| Skip["No notification queued"]
    Policy -->|yes| Recipients["Apply recipients, escalation, and opt-outs"]
    Recipients --> Email["Queue one email job per eligible recipient"]
    Recipients --> Webhook{"Webhook configured?"}
    Webhook -->|yes| Post["POST bounded alert payload"]
    Webhook -->|no| Done["Record delivery state"]
    Email --> Done
    Post --> Delivered{"HTTP success?"}
    Delivered -->|yes| Sent["Mark sent"]
    Delivered -->|no| Retry["Keep failed for next worker run"]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Reconcile,State,Email,Done,Sent success
    class Skip,Retry blocked
    class Policy,Webhook,Delivered decision
```
---

## Settings and privacy

---

Company administrators configure recipients, minimum severity, and escalation
delay. Each user can opt out of alert email without changing company policy.
Webhook URLs remain in deployment configuration and are not exposed through
the API or saved in delivery rows. Delivery history retains channel, recipient
label, status, timestamps, and email job ID where applicable.
---

## Code references

---

- `backend/app/balance_sheets/analysis_settings.py`
- `backend/app/balance_sheets/analysis_notifications.py`
- `backend/app/procrastinate_tasks/analysis_notification_tasks.py`
- `backend/app/api/analysis_routes/analysis_routes.py`
- `frontend/src/app/balance-sheets/BalanceSheetAnalysisPanel.tsx`
---

## See also

---

- [App API reference](../api.md#balance-sheet-analysis)
- [Feature implementation notes](../features.md#deterministic-balance-sheet-analysis)
