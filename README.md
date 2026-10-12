# Balance Sheet Analysis

---

![Python](https://img.shields.io/badge/python-3.14-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.142+-green?logo=fastapi)
![React](https://img.shields.io/badge/React-19+-blue?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-6+-blue?logo=typescript)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql)
![Valkey](https://img.shields.io/badge/Valkey-7+-red?logo=valkey)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Overview

A company financial analysis tool for importing balance sheets, reviewing
annual and quarterly trends, comparing companies, saving management reviews,
and asking questions grounded in stored financial data. Company access is
checked on the server with MysticAuth's Policy-Based Access Control (PBAC).

MysticAuth provides authentication, session management, and the PBAC engine.
This application owns its financial models, company-scoped policies, analysis
services, and product UI. The ownership split is reflected in the code and
documentation trees.

---

## Screenshots

### Product overview

![Balance Sheet Analysis product overview](screenshots/app/landing.png)

<details>
<summary>See all 9 application screenshots</summary>

---

#### Sign in

![Balance Sheet Analysis sign-in page](screenshots/app/login.png)

---

#### Companies

![Companies list](screenshots/app/companies.png)

---

#### Company detail

![Company profile, provenance, and trends](screenshots/app/company_detail.png)

---

#### Balance sheet analysis

![Deterministic balance-sheet metrics and warnings](screenshots/app/analysis.png)

---

#### Financial statements

![Annual income and cash-flow statements](screenshots/app/financial_statements.png)

---

#### Company comparison

![Selected-company comparison](screenshots/app/comparison.png)

---

#### Management review

![Saved management review and review status](screenshots/app/management_review.png)

---

#### Company chat

![Company-scoped question and response](screenshots/app/llm_chat.png)

</details>

---

## Architecture

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart LR
    Browser["Browser: app UI + MysticAuth UI"] --> API["FastAPI: app routes + MysticAuth routes"]
    API --> Auth["MysticAuth session and PBAC"]
    API --> DB[("PostgreSQL")]
    API --> Cache[("Valkey")]
    API --> Finance["yfinance"]
    API --> LLM["Configured LLM provider"]
    Worker["Procrastinate worker"] --> DB
    Worker --> Notify["Email and optional webhook"]
    classDef success fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef blocked fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    class API,Auth,DB,Cache,Worker success
```

---

## Product features

- Import and refresh balance sheets with source provenance and version history.
- Compare explicitly selected companies and analyze trends, liquidity,
  leverage, warnings, and optional currency normalization.
- Import curated income and cash-flow data, including quarterly and TTM
  analysis.
- Save review snapshots with comments, assignments, sign-offs, and HTML export.
- Ask company-scoped LLM questions using selected stored financial data.
- Configure durable analysis alerts and email or optional webhook delivery.
- Support English, Hindi, Marathi, and Gujarati for the app's own UI.

All company data and company-scoped API operations are authorized server-side.
See [Company Access Control](docs/app/access-control/README.md).

---

## Stack

- **Backend:** FastAPI, SQLAlchemy async, Alembic, and Python.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Chakra UI, and Recharts.
- **Data:** PostgreSQL, Valkey, yfinance, and a configurable OpenAI-compatible
  LLM provider.
- **Background jobs:** Procrastinate with PostgreSQL-backed task storage.
- **Authentication and authorization:** MysticAuth, vendored in
  `backend/mystic_auth/` and `frontend/src/mystic_auth/`.
- **Deployment:** Docker Compose development, local-prod tunnel modes, and
  server-hosted production mode.

---

## Quickstart

Use Docker for the full development stack:

```bash
./scripts/mystic_auth/env-tools/setup-env/setup-env.sh
./scripts/mystic_auth/docker/dev/dev-up.sh
```

The helper creates the split local environment files when needed, starts both
Compose layers, waits for healthy services, and tails application logs. Then
follow [Application Quickstart](docs/app/quickstart.md) to create the
MysticAuth system superuser, seed app policies, and grant a user's company
access.

---

## Documentation

- [App documentation](docs/app/README.md): app architecture, setup, API,
  features, access control, and scripts.
- [Application flow diagrams](docs/app/flows/README.md): Mermaid diagrams for
  company access, imports, analysis, chat, reviews, and alert delivery.
- [MysticAuth documentation](docs/mystic_auth/README.md): authentication,
  PBAC, infrastructure, testing, CI, and deployment.
- [MysticAuth template usage](docs/mystic_auth/template-usage/overview.md):
  downstream ownership and upstream synchronization.
- [Contributor guide](CONTRIBUTING.md): local checks and contribution workflow.
- [Security policy](SECURITY.md): vulnerability reporting.

---

## Testing

CI runs the backend, frontend, integration, security, browser, and deployment
checks. The backend cumulative coverage gate is 90%; frontend coverage gates
remain 90%. See [MysticAuth Testing](docs/mystic_auth/testing/overview.md) for
the full pipeline and commands.

---

## License

MIT. See [LICENSE](LICENSE).

---
