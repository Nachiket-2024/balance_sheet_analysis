// border.default is too close to bg.canvas for a search box sitting
// directly on the page (e.g. UsersPage/PoliciesPage), so this uses a fixed
// higher-contrast border plus bg.surface for a raised look, and a
// brand-color focus ring instead of the default gray one.
// Mirrors the backend's SEARCH_QUERY_MAX_LENGTH (core/search_query.py) so
// typing/pasting gets instant feedback instead of a 422 after submit. Not a
// security boundary on its own; the backend still enforces it independently.
export const SEARCH_QUERY_MAX_LENGTH = 100;

// The border/hover/focus treatment for every bordered text input is baked
// directly into ui/inputs/Input.tsx/ui/inputs/Textarea.tsx's Tailwind
// classes, shared by every plain form field, StyledSelect's trigger, etc.
