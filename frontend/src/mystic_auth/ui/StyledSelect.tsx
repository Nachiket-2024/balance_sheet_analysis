import React, { useMemo } from "react";
import { Portal, Select, visuallyHiddenStyle, createListCollection } from "@chakra-ui/react";
import type { SelectRootProps } from "@chakra-ui/react";

export interface StyledSelectOption {
    label: string;
    value: string;
}

interface StyledSelectProps {
    value: string;
    onChange: (value: string) => void;
    options: StyledSelectOption[];
    ariaLabel: string;
    size?: SelectRootProps["size"];
    w?: SelectRootProps["width"];
    textTransform?: SelectRootProps["textTransform"];
    disabled?: boolean;
    title?: string;
}

/**
 * Filter/inline-picker dropdown, shared by every select-shaped control in
 * the app (role/verified/status filters, event/resource/result filters,
 * the inline role-change picker, policy-assign). Wraps Chakra's actual
 * `Select` (a styled, JS-driven listbox) rather than `NativeSelect`: a
 * native `<select>` can have its closed-state trigger restyled, but the
 * OPEN dropdown is always the browser/OS's own unstyled native menu -
 * exactly the "still looks like a plain HTML dropdown" gap this replaces.
 * `Select.Content` below is a real styled popover instead.
 */
const StyledSelect: React.FC<StyledSelectProps> = ({
    value, onChange, options, ariaLabel, size = "md", w, textTransform, disabled, title,
}) => {
    const collection = useMemo(() => createListCollection({ items: options }), [options]);

    return (
        <Select.Root
            collection={collection}
            value={[value]}
            onValueChange={(details) => onChange(details.value[0] ?? "")}
            size={size}
            width={w}
            disabled={disabled}
            title={title}
        >
            <Select.HiddenSelect aria-label={ariaLabel} />
            {/* Chakra's Select.Trigger auto-wires an aria-labelledby
                pointing at Select.Label's id whether or not one is actually
                rendered - omit this and the trigger's accessible name
                resolves to nothing (aria-labelledby pointing at a
                nonexistent id wins over Select.HiddenSelect's own
                aria-label above, it doesn't fall back to it), so every
                assistive-tech user would hear these as unlabeled controls.
                Visually hidden since every caller already shows its own
                on-screen label (a field label, a "Filter by X" heading)
                right next to this. */}
            <Select.Label css={visuallyHiddenStyle}>{ariaLabel}</Select.Label>
            <Select.Control>
                <Select.Trigger
                    borderColor="gray.400"
                    bg="bg.surface"
                    textTransform={textTransform}
                    // Chakra's own sm/md Select sizes only change the
                    // trigger's height/padding - both share the same 14px
                    // textStyle. Explicit override so this matches the
                    // 15px now used for table text/buttons elsewhere.
                    fontSize="15px"
                    _hover={{ borderColor: "gray.600" }}
                    _focusVisible={{ borderColor: "brand.solid", boxShadow: "0 0 0 1px var(--chakra-colors-brand-solid)" }}
                    _dark={{ borderColor: "gray.600", _hover: { borderColor: "gray.400" } }}
                >
                    <Select.ValueText />
                    <Select.IndicatorGroup>
                        <Select.Indicator />
                    </Select.IndicatorGroup>
                </Select.Trigger>
            </Select.Control>
            <Portal>
                <Select.Positioner>
                    {/* No explicit zIndex here: Chakra's own Select recipe
                        already computes it as popover + a dynamic
                        --layer-index (the same mechanism Dialog uses for its
                        own z-index) so a nested layer like this one, opened
                        from inside a Dialog, automatically stacks above it.
                        A hardcoded flat zIndex="popover" here used to
                        clobber that calc, so this dropdown's list rendered
                        BEHIND the dialog it lives in instead of on top. */}
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
                                textTransform={textTransform}
                                // Three states, three distinct treatments so
                                // none of them can be mistaken for another:
                                // plain/no-fill at rest, a solid brand fill
                                // + white text on hover (the same "fills up"
                                // feedback used elsewhere in the app, e.g.
                                // Delete row-actions), and a colored,
                                // bold-text tinted wash for the persisted
                                // selection (already reinforced by its own
                                // checkmark). `brand.selected` (not
                                // `brand.subtle`, one step lighter) - subtle
                                // was too pale to read as "selected" at a
                                // glance in light mode, the same
                                // too-faint-tint issue `brand.selected`
                                // already exists to fix for the sidebar's
                                // own active-link background.
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

export default StyledSelect;
