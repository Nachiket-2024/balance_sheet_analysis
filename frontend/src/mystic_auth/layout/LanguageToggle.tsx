import React, { useMemo } from "react";
import { Portal, Select, createListCollection, visuallyHiddenStyle } from "@chakra-ui/react";

import {
    LANGUAGE_MODES,
    LANGUAGE_MODE_LABELS,
    useLanguageStore,
    type LanguageMode,
} from "../store/languageStore";
import translations from "../translations/translations";
import { ICON_BUTTON_PROPS } from "../ui/styles/buttonStyles";

/**
 * Language switch, backed by store/languageStore.ts (persists to
 * localStorage, drives the translations module). A plain click-to-open
 * dropdown (Chakra's Select, not a typeable Combobox) - with only five
 * options (see LANGUAGE_MODES: three plain languages plus two mixed
 * "English chrome + translated page" modes), a search box isn't earning its
 * keep the way it would past a few dozen languages; this matches how most
 * real-world language switchers (GitHub, Wikipedia, Google) work at this
 * scale. Click to open, click an option, closes - the current selection
 * stays visible at rest either way.
 *
 * Uses chromeLanguage (always English unless a plain hi/mr mode is active),
 * not the global page language, for its own label/aria-label - it lives in
 * Navbar, which is chrome, same reasoning as Navbar.tsx/Sidebar.tsx.
 */
const LanguageToggle: React.FC = () => {
    const mode = useLanguageStore((s) => s.mode);
    const setMode = useLanguageStore((s) => s.setMode);
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    const t = translations.getFixedT(chromeLanguage, "layout");

    const options = useMemo(
        () => LANGUAGE_MODES.map((m) => ({ value: m, label: LANGUAGE_MODE_LABELS[m] })),
        []
    );
    const collection = useMemo(() => createListCollection({ items: options }), [options]);

    return (
        <Select.Root
            collection={collection}
            value={[mode]}
            onValueChange={(details) => {
                const next = details.value[0] as LanguageMode | undefined;
                if (next) setMode(next);
            }}
            size="sm"
            width="170px"
        >
            <Select.HiddenSelect aria-label={t("language")} />
            {/* See StyledSelect.tsx's matching comment: without this,
                Select.Trigger's auto-wired aria-labelledby (pointing at
                Select.Label's id) wins over Select.HiddenSelect's aria-label
                above, leaving the trigger unlabeled for assistive tech.
                Visually hidden since this lives in the navbar next to
                ThemeToggle, with no separate on-screen label. */}
            <Select.Label css={visuallyHiddenStyle}>{t("language")}</Select.Label>
            <Select.Control>
                {/* Same border/bg/hover treatment as ThemeToggle's IconButton -
                    shares ICON_BUTTON_PROPS directly so the two can't drift
                    apart the way the old hand-duplicated values could. */}
                <Select.Trigger
                    fontSize="15px"
                    {...ICON_BUTTON_PROPS}
                >
                    <Select.ValueText />
                    <Select.IndicatorGroup>
                        <Select.Indicator />
                    </Select.IndicatorGroup>
                </Select.Trigger>
            </Select.Control>
            <Portal>
                <Select.Positioner>
                    <Select.Content
                        borderWidth="1px"
                        borderColor="border.default"
                        bg="bg.surface"
                        boxShadow="lg"
                        fontSize="15px"
                    >
                        {options.map((option) => (
                            <Select.Item
                                key={option.value}
                                item={option}
                                _highlighted={{ bg: "brand.solid", color: "white" }}
                                _selected={{ bg: "brand.selected", color: "brand.fg", fontWeight: "semibold" }}
                            >
                                <Select.ItemText>{option.label}</Select.ItemText>
                                <Select.ItemIndicator />
                            </Select.Item>
                        ))}
                    </Select.Content>
                </Select.Positioner>
            </Portal>
        </Select.Root>
    );
};

export default LanguageToggle;
