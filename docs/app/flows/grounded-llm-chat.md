# Grounded LLM Chat Flow
---

Chat is scoped to one company and uses that company's persisted financial
records to build context. The user question and generated answer are not stored
in the usage table.
---

## Request flow

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    User["User submits company, years, question"] --> Company["Load company"]
    Company --> Auth["Check llm:chat for company scope"]
    Auth -->|denied| Forbidden["403 response"]
    Auth -->|allowed| Rows["Load selected balance sheets and statements"]
    Rows --> Context["Build curated deterministic context"]
    Context --> Budget{"Daily character budget available?"}
    Budget -->|no| Limited["429 budget exceeded"]
    Budget -->|yes| Provider["Call configured LLM provider"]
    Provider -->|success| Record["Record counts and success status"]
    Record --> Answer["Return answer"]
    Provider -->|runtime failure| Failure["Record bounded failure metadata; return 502"]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class Context,Record,Answer success
    class Forbidden,Limited,Failure blocked
    class Budget decision
```
---

## Privacy and limits

---

The application sends selected financial context and the question to the
configured provider. The local usage record stores character counts, provider,
model, status, and a bounded error code; it does not store prompt text or API
keys. Requests are rate limited and checked against the per-account daily
character budget before the provider call.
---

## Code references

---

- `backend/app/api/llm_routes/llm_routes.py`
- `backend/app/llm/llm_service.py`
- `backend/app/llm/llm_usage.py`
- `frontend/src/app/llm/LlmChatWidget.tsx`
---

## See also

---

- [App API reference](../api.md#llm-chat)
- [App setup](../setup.md#environment-variables-this-app-adds)
- [Analysis alerts and delivery](analysis-alerts-and-delivery.md)
