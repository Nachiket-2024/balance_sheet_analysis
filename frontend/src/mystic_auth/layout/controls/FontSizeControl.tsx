import React, { useMemo } from "react";
import { Select as SelectPrimitive } from "radix-ui";
import { Check, ALargeSmall } from "lucide-react";

import { FONT_SIZES, useFontSizeStore, type FontSize } from "../../store/fontSizeStore";
import translations from "../../translations/translations";
import { useLanguageStore } from "../../store/languageStore";
import { buttonVariants } from "../../ui/buttons/button-variants";
import { cn } from "../../ui/styles/classNames";

/**
 * Global text-size control, backed by store/fontSizeStore.ts. A Select
 * dropdown, same pattern as LanguageToggle. The trigger stays a fixed icon,
 * not the current value, so it reads as a settings control.
 *
 * Uses chromeLanguage, not the page-wide translation language, since this is
 * Navbar chrome (same reasoning as ThemeToggle/LanguageToggle).
 */
const FontSizeControl: React.FC = () => {
    const chromeLanguage = useLanguageStore((s) => s.chromeLanguage);
    const t = translations.getFixedT(chromeLanguage, "layout");
    const fontSize = useFontSizeStore((s) => s.fontSize);
    const setFontSize = useFontSizeStore((s) => s.setFontSize);

    const options = useMemo(
        () => FONT_SIZES.map((size) => ({ value: size, label: t(`fontSize.${size}`) })),
        [t]
    );

    return (
        <SelectPrimitive.Root
            value={fontSize}
            onValueChange={(next) => setFontSize(next as FontSize)}
        >
            {/* See LanguageToggle.tsx: real native <select>, aria-hidden,
                purely for the standard hidden-select fallback. */}
            <select
                aria-label={t("fontSize.label")}
                aria-hidden="true"
                tabIndex={-1}
                className="sr-only"
                value={fontSize}
                onChange={(e) => setFontSize(e.target.value as FontSize)}
            >
                {options.map((option) => (
                    <option key={option.value} value={option.value}>
                        {option.label}
                    </option>
                ))}
            </select>
            {/* Icon-only trigger, matching LanguageToggle's icon-button
                treatment (see design/dashboard.html's .icon-btn) - shares
                Button's "icon"/"icon-sm" variant classes with
                ThemeToggle/LanguageToggle so the styles can't drift apart. */}
            <SelectPrimitive.Trigger
                aria-label={t("fontSize.label")}
                className={cn(buttonVariants({ variant: "icon", size: "icon-sm" }))}
            >
                {/* See LanguageToggle.tsx: sr-only, not display:none, keeps
                    the current size's name in the accessibility tree even
                    though the trigger only shows an icon. */}
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
                <ALargeSmall size={16} aria-hidden="true" />
            </SelectPrimitive.Trigger>
            <SelectPrimitive.Portal>
                <SelectPrimitive.Content
                    position="popper"
                    sideOffset={4}
                    className="z-[1500] w-max max-w-[min(20rem,calc(100vw-2rem))] overflow-hidden rounded-md border border-brand-border bg-popover p-0 text-popover-foreground shadow-md data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
                >
                    {/* See LanguageToggle.tsx: the icon-only trigger has no
                        width of its own for the popover to size from. */}
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

export default FontSizeControl;
