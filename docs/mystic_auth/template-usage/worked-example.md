# Worked Example: Adding a New Domain, End to End
---

[Using This Repository as a Template](overview.md) describes the pieces (ownership tiers, `sdk.py`/`sdk.ts`, PBAC usage, shared-chrome extension points) individually. This page wires them together for one fake domain (`projects`) so you have something to copy and rename rather than assemble from scratch. None of this is upstream code to run as-is; it's a template for the shape your own feature takes.

---

## 1. Backend: model, schema, router

```
backend/app/projects/
    __init__.py
    project_model.py     # SQLAlchemy model
    project_schema.py     # Pydantic request/response schemas
    project_crud.py       # DB queries
    project_routes.py     # APIRouter, including the PBAC usage snippet below
```

`project_routes.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.sdk import require_authorization, database

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/")
async def list_all_projects(
    current_user: dict = Depends(require_authorization("projects:read", "projects")),
    db: AsyncSession = Depends(database.get_session)
):
    return await project_crud.get_all(db)
```

`resource_type`/`action` don't need to be `Permission` enum values; any non-empty string works, granted via a policy. Custom actions remain app-owned and are still protected by the privilege-escalation guard, so seed the first app grant from an app-owned migration or policy bootstrap before using the management API.

---

## 2. Mount it

```python
# backend/app/main.py, an existing "shared, extend in place" file
from .projects.project_routes import router as projects_router
# ...
app.include_router(projects_router)
```

---

## 3. Add the migration

```bash
alembic -c backend/alembic.ini revision --autogenerate -m "add projects table"
alembic -c backend/alembic.ini upgrade head
```

See [Database Design: migrations](../database/design.md#migrations). No `create_all()`, ever.

---

## 4. Grant access via a policy, not a role

Nothing above grants anyone access by itself. `require_authorization` only checks whether the caller holds an active policy covering `("projects:read", "projects")`. Create one (via `/policies` in the UI, or the `POST /authorization/policies` API) and assign it to whichever users/roles should see this data. See [Policy JSON Examples](../authorization/policy-examples.md) if you want a template to start from.

---

## 5. Frontend: page, route, nav link

```tsx
// frontend/src/app/projects/ProjectsPage.tsx
import { PageContainer, DataTable, type DataTableColumn } from "../app_sdk"; // your own re-exports, see app_sdk.ts
import { IfCan } from "../sdk";
import { APP_PERMISSIONS } from "../access/permissions"; // your own action vocabulary, see frontend-customization.md#shared-chrome-extension-points

const ProjectsPage: React.FC = () => {
    // fetch + render your projects here, see an existing mystic_auth/*
    // page for the query/table pattern this template already uses
    return <PageContainer title="Projects">{/* ... */}</PageContainer>;
};

export default ProjectsPage;
```

```tsx
// frontend/src/app/App.tsx, add the route
import { AppLayout, ProtectedRoute, trackedLazy, type NavItem } from "./sdk";
const ProjectsPage = trackedLazy(() => import("./projects/ProjectsPage"));

const EXTRA_NAV_ITEMS: NavItem[] = [
    { label: "Projects", to: "/projects", permission: APP_PERMISSIONS.PROJECTS_READ },
];

// inside <Routes>:
<Route path="/projects" element={
    <ProtectedRoute permission={APP_PERMISSIONS.PROJECTS_READ}>
        <AppLayout extraNavItems={EXTRA_NAV_ITEMS}>
            <ProjectsPage />
        </AppLayout>
    </ProtectedRoute>
} />
```

That's the whole loop: a gated backend route, a migration for its table, a policy that actually grants access, and a frontend page that's route-protected and only advertised in the sidebar to callers who can see it. Every other domain you add follows the same five steps.

---

## 6. A pre-auth landing page

`/projects` above lives *inside* the authenticated app shell (`AppLayout`, `ProtectedRoute`). Not every page does - a marketing/landing page at `/` needs to render before login, with no sidebar, no nav item, and no permission check. `frontend/src/app/landing_page/LandingPage.tsx` is the reference example for this second shape: a plain page, route-mounted directly, that only reads from `../sdk` (here, `useAuthStore` to bounce an already-signed-in visitor straight to `/dashboard`, and `APP_NAME` for the header - the same values `LoginPage`/`SignupPage` use).

```tsx
// frontend/src/app/landing_page/LandingPage.tsx
import { Navigate } from "react-router";
import { useAuthStore, APP_NAME } from "../sdk";

const LandingPage: React.FC = () => {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    if (isAuthenticated) return <Navigate to="/dashboard" replace />;

    return <>{/* hero, pitch, CTAs into /signup and /login */}</>;
};

export default LandingPage;
```

```tsx
// frontend/src/app/App.tsx: "/" mounts LandingPage directly, no AppLayout/
// ProtectedRoute wrapper, and no NavItem - a landing page isn't a
// sidebar destination.
const LandingPage = trackedLazy(() => import("./landing_page/LandingPage"));
// inside <Routes>:
<Route path="/" element={<LandingPage />} />
```

Any other pre-auth or chrome-free page (a public status page, a docs page embedded in the app, an unsubscribe-confirmation page) follows this same shape: its own directory under `app/`, mounted as a bare `<Route>`, reading only what it needs from `../sdk`. `frontend/src/app/legal/PrivacyPolicyPage.tsx` and `TermsOfServicePage.tsx` (routes `/privacy`, `/terms`) are a real instance of this pattern already in the template, built on `AuthLayout` instead of a fully bare page since they need the theme/language toggle header but not the sidebar.

---
