// border.default (theme/system.ts) is only one step off bg.canvas in both
// modes (gray.200 vs gray.100 light, gray.700 vs gray.900 dark), fine for an
// input sitting on a Card's bg.surface (a bigger jump), but a filter input
// placed directly on bg.canvas (e.g. UsersPage/PoliciesPage's search box)
// read as barely-there against the page itself. A fixed, higher-contrast
// border, one more step out in each direction, keeps it clearly visible on
// bg.canvas without depending on Card ever being underneath it. `bg.surface`
// gives it a filled, raised look instead of a transparent outline sitting
// flush with the page, and the focus ring ties keyboard/click focus to the
// same brand color buttons already use, rather than the browser/Chakra
// default gray ring, which read as an unstyled/unfinished form control.
export const SEARCH_INPUT_PROPS = {
    bg: "bg.surface",
    borderColor: "gray.400",
    _hover: { borderColor: "gray.600" },
    _focus: { borderColor: "brand.solid", boxShadow: "0 0 0 1px var(--chakra-colors-brand-solid)" },
    _dark: { borderColor: "gray.600", _hover: { borderColor: "gray.400" } },
};
