# Access Control: Companies and Groups

The company-hierarchy access model: a CEO sees only their own company, a group executive sees their whole group, an analyst is scoped the same way, all built on top of mystic-auth's Policy-Based Access Control.

- **[overview.md](overview.md)**: the requirement, the hierarchy diagram, and how a policy is shaped
- **[enforcement.md](enforcement.md)**: the two different code paths (list vs. single-resource) that check these conditions
- **[baseline-policies.md](baseline-policies.md)**: the two unconditioned, ready-to-assign policies seeded automatically on every `docker compose up`
- **[onboarding.md](onboarding.md)**: why a fresh account starts with none of this, and the walkthrough to grant it
- **[roles-are-metadata.md](roles-are-metadata.md)**: why `User.role` never decides access, only policies do
