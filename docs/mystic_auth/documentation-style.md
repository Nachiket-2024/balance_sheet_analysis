# Documentation Style
---

*New to a term here? See the [Glossary](glossary/README.md).*

The conventions every page under `docs/mystic_auth/` follows, written down once instead of re-derived
per page. Not enforced by tooling; kept consistent by review.

---

## Page structure

1. `# Title` on the first line, then a bare `---` divider, then (where the term glossary applies to
   that topic) an italic "New to a term here? See the X Glossary" line, linking the real glossary
   path for that page (e.g. `../glossary/infrastructure.md`) - see this file's own line 4 above for
   a real example.
2. Sections use `## Heading`, each preceded and followed by a bare `---` divider line. A short intro
   paragraph comes before the first section, explaining what the page covers and why it was split out
   from wherever it lives in the doc tree.
3. A page that grew past a readable size (roughly 300-350 lines) gets split into a folder: a
   `README.md` holding the index/shared intro plus a `## Pages` list, and one file per sub-topic.
   Every split keeps its own file focused on one topic, named for what it documents, not a vague
   `part1.md`/`misc.md`.
4. Ends with a `## See also` (or equivalent) section linking sibling docs, when the topic connects to
   others readers are likely to want next.

---

## Breaking up long paragraphs

- A paragraph covering more than 3-4 distinct points reads like a wall of text. Split it into a
  numbered list (steps/order matters) or a bulleted list (independent facts), per the rule below.
- Keep a short lead-in sentence before the list explaining what it covers, then let the list carry
  the detail instead of run-on prose.

---

## Numbered procedure style

- A sequence of steps the reader actually performs (commands to run, a decision order the code
  follows) is numbered (`1.`, `2.`, ...), not bulleted.
- A sequence of independent facts about the same topic (not a walkthrough) stays bulleted (`-`), even
  when there are many of them.
- Numbered lists describing backend order-of-operations name the actual check/consequence at each
  step (e.g. "account not found -> not verified -> not active -> wrong password"), not a vague
  "do the next check."

---

## Mermaid diagram rules

- Every page describing a request/response or multi-step flow gets its own diagram, not shared with
  a neighboring page - the reason several docs get split by flow in the first place (see
  [Login](authentication/login.md) for the login lockout/rate-limit diagram as an example).
- Diagrams open with `%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%` for a consistent
  connector color, then a `flowchart TD` (top-down) unless the flow is genuinely left-right shaped.
- Labels stay short: a node name plus, where useful, a one-line clarifying subtext after `\n`. Avoid
  full sentences inside a node.
- `classDef` blocks color-code outcomes consistently across the whole doc tree: success states green
  (`fill:#dcfce7,stroke:#16a34a`), blocked/error states red (`fill:#fee2e2,stroke:#dc2626`), decision
  points blue (`fill:#eff6ff,stroke:#3b82f6`).
- A page that has no flow worth diagramming says so explicitly (`> Diagram omitted. See the
  surrounding prose, tables, or numbered steps for the same flow.`) rather than silently having none,
  so it's clear the omission was a choice.

---

## Code reference conventions

- A file or symbol referenced from prose uses its path relative to the repo root in backticks (e.g.
  `` `backend/mystic_auth/auth/login/login_service.py` ``), not just a bare filename, so it's
  unambiguous which of several same-named files across `backend/mystic_auth/` and
  `frontend/src/mystic_auth/` is meant.
- A cross-doc link that points at a specific claim, not just the file, links the anchor (e.g.
  `../security/decisions-auth.md#role-is-never-used-to-decide-access`), not just the page.
- Component/route tables (see [Login](authentication/login.md#components) for the pattern) list
  `File` and `Role` columns rather than prose, when a page's whole subject is "what talks to what."

---

## Tutorial section format

- Every doc assumes a reader new to this specific topic, not new to programming: a technical term
  gets a plain-language explanation the first time it matters, either inline (short terms) or via a
  link into the relevant [Glossary](glossary/README.md) page (longer/reused terms).
- "Why" precedes "how" wherever a design choice isn't self-evident from the code: a paragraph
  explaining the reasoning comes before or alongside the mechanism, not left for the reader to infer
  from a diff.
- Edge cases get their own `## Edge cases` (or similarly named) section near the end of a page,
  rather than being folded into the main walkthrough where they'd interrupt the primary flow.

---
