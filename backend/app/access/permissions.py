"""
Action vocabulary for this app's own PBAC-protected resources (companies,
financial data, reviews, and LLM operations): the domain-specific counterpart to
mystic_auth.authorization.permissions.Permission.

Per mystic-auth's template-usage.md: "Actions don't need to be predefined
enums, pass any string and grant it through data-driven policies." These
constants exist purely so every route/seed script/test spells the same
action string identically; nothing about PBAC itself requires this file.

Naming mirrors mystic_auth's own "<resource>:<action>" convention.
"""

# Resource types (Policy.resource_type)
RESOURCE_COMPANY = "company"
RESOURCE_BALANCE_SHEET = "balance_sheet"
RESOURCE_LLM = "llm"

# Company actions
COMPANY_READ = "company:read"
COMPANY_CREATE = "company:create"
COMPANY_UPDATE = "company:update"
COMPANY_DELETE = "company:delete"

# Balance sheet actions: read is granted to both analysts and
# top-management/CEOs; import/delete are analyst-only (data-entry duties),
# per this session's access-model decision.
BALANCE_SHEET_READ = "balance_sheet:read"
BALANCE_SHEET_IMPORT = "balance_sheet:import"
BALANCE_SHEET_DELETE = "balance_sheet:delete"

# LLM chat is gated per company with the same scope as its source data.
LLM_CHAT = "llm:chat"
# Provider usage and operations views are gated separately from company chat.
LLM_USAGE_READ_ALL = "llm:usage_read_all"
