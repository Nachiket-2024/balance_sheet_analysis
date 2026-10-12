import React, { useMemo } from "react";
import { Select as SelectPrimitive } from "radix-ui";
import { Check, Languages } from "lucide-react";

import {
    LANGUAGE_MODES,
    LANGUAGE_MODE_LABELS,
    useLanguageStore,
    type LanguageMode,
} from "../../store/languageStore";
import translations from "../../translations/translations";
import { buttonVariants } from "../../ui/buttons/button-variants";
import { cn } from "../../ui/styles/classNames";

/**
 * Language switch, backed by store/languageStore.ts. A plain click-to-open
 * dropdown (Radix's Select, not a typeable Combobox): with only five
 * options a search box isn't worth it.
 *
 * Uses chromeLanguage, not the global page language, since this is Navbar
 * chrome (same reasoning as Navbar.tsx/Sidebar.tsx).
 */
const LanguageToggle: React.FC = () => {
    const mode = useLanguageStore((s) => s.mode);
    const setMode = useLanguageStore((s) => s.setMode);
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    useLanguageStore((s) => s.languageRevision);
    const t = translations.getFixedT(chromeLanguage, "layout");

    const options = useMemo(
        () => LANGUAGE_MODES.map((m) => ({ value: m, label: LANGUAGE_MODE_LABELS[m] })),
        []
    );

    return (
        <SelectPrimitive.Root
            value={mode}
            onValueChange={(next) => setMode(next as LanguageMode)}
        >
            {/* Real native <select>, kept in sync and aria-hidden - see
                StyledSelect.tsx's identical comment: not for styling, just
                the standard hidden-select fallback (form autofill, and what
                this app's test suite drives via userEvent.selectOptions). */}
            <select
                aria-label={t("language")}
                aria-hidden="true"
                tabIndex={-1}
                className="sr-only"
                value={mode}
                onChange={(e) => setMode(e.target.value as LanguageMode)}
            >
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
            {/* Icon-only trigger, matching the design's navbar icon buttons
                (see design/dashboard.html's .icon-btn) - shares Button's
                "icon"/"icon-sm" variant classes with ThemeToggle so the
                styles can't drift apart. The dropdown itself is unchanged;
                only the trigger's visible content is a fixed icon instead
                of the current language label. */}
            <SelectPrimitive.Trigger
                aria-label={t("language")}
                className={cn(buttonVariants({ variant: "icon", size: "icon-sm" }))}
            >
                {/* sr-only, not display:none: this
                    keeps the current language's name in the accessibility
                    tree (a screen reader announces it alongside the trigger's
                    aria-label) even though the trigger only shows an icon -
                    display:none would drop it from the accessibility tree
                    entirely, silently regressing that. */}
                {/* Wrapper span, not className on Value itself: Radix's
                    SelectValue destructures `className` (and `style`) out of
                    its props and never applies either to the span it
                    renders (@radix-ui/react-select's SelectValue2), so
                    className="sr-only" directly on Value silently did
                    nothing - the label rendered fully visible next to the
                    icon. */}
                <span className="sr-only">
                    <SelectPrimitive.Value />
                </span>
                <Languages size={16} aria-hidden="true" />
            </SelectPrimitive.Trigger>
            <SelectPrimitive.Portal>
                <SelectPrimitive.Content
                    position="popper"
                    sideOffset={4}
                    // Fade-only motion keeps Radix's popper transform free for positioning.
                    className="z-[1500] w-max max-w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-md border border-brand-border bg-popover p-0 text-popover-foreground shadow-md data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
                >
                    {/* min-w-max-content, not the trigger's own width (unlike
                        StyledSelect): the icon-only trigger is a fixed ~32px
                        square with nothing for the popover to size itself
                        from, so it needs to size from its longest option
                        instead or every label wraps one character per
                        line. */}
                    <SelectPrimitive.Viewport className="dropdown-scroll-area max-h-80 overflow-y-auto p-1 min-w-max">
                        {options.map((option) => (
                            <SelectPrimitive.Item
                                key={option.value}
                                value={option.value}
                                className={cn(
                                    "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-2 pr-6 text-sm outline-none overflow-hidden text-ellipsis whitespace-nowrap",
                                    "data-[highlighted]:bg-brand-solid data-[highlighted]:text-brand-contrast",
                                    "data-[state=checked]:bg-[var(--brand-200)] data-[state=checked]:text-brand-fg data-[state=checked]:font-semibold data-[state=checked]:shadow-[inset_0_0_0_1.5px_var(--brand-500)] dark:data-[state=checked]:bg-brand-selected dark:data-[state=checked]:shadow-[inset_0_0_0_1.5px_var(--brand-400)] data-[state=checked]:data-[highlighted]:bg-brand-solid data-[state=checked]:data-[highlighted]:text-brand-contrast data-[state=checked]:data-[highlighted]:shadow-none"
                                )}
                            >
                                <SelectPrimitive.ItemIndicator className="absolute right-2 inline-flex items-center">
                                    <Check size={14} aria-hidden="true" />
                                </SelectPrimitive.ItemIndicator>
                                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                            </SelectPrimitive.Item>
                        ))}
                    </SelectPrimitive.Viewport>
                </SelectPrimitive.Content>
            </SelectPrimitive.Portal>
        </SelectPrimitive.Root>
    );
};

export default LanguageToggle;
