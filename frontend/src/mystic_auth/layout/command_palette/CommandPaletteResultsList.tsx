import React from "react";
import { useTranslation } from "react-i18next";

import { GROUP_LABEL_KEY, type Result } from "./CommandPaletteResults";
import AppTooltip from "../../ui/feedback/AppTooltip";

interface CommandPaletteResultsListProps {
    filtered: Result[];
    kindCount: number;
    activeIndex: number;
    setActiveIndex: (index: number) => void;
    goTo: (to: string) => void;
}

/** CommandPalette's result list: grouped rows with a header wherever the
 * result kind changes, and the currently-highlighted row (keyboard or hover)
 * shown selected. */
const CommandPaletteResultsList: React.FC<CommandPaletteResultsListProps> = ({
    filtered,
    kindCount,
    activeIndex,
    setActiveIndex,
    goTo,
}) => {
    const { t } = useTranslation("layout");

    if (filtered.length === 0) {
        return (
            <p className="px-4 py-6 text-center text-fg-muted text-sm">
                {t("commandPalette.noResults")}
            </p>
        );
    }

    return (
        <>
            {filtered.map((item, i) => {
                const Icon = item.icon;
                const isActive = i === activeIndex;
                // A group header renders right before the first item of that
                // kind - `filtered` is already ordered pages-then-content-then-users.
                const isFirstOfKind = kindCount > 1 && (i === 0 || filtered[i - 1].kind !== item.kind);
                return (
                    <React.Fragment key={`${item.kind}:${item.to}:${item.label}`}>
                        {isFirstOfKind && (
                            <p className={`px-4 ${i === 0 ? "pt-1" : "pt-3"} pb-1 text-xs font-semibold text-fg-muted uppercase`}>
                                {t(GROUP_LABEL_KEY[item.kind])}
                            </p>
                        )}
                        <button
                            type="button"
                            className={`flex items-center gap-3 w-full min-w-0 text-left px-4 py-2.5 cursor-pointer text-fg-default ${isActive ? "bg-brand-selected" : "bg-transparent"}`}
                            onMouseEnter={() => setActiveIndex(i)}
                            onClick={() => goTo(item.to)}
                        >
                            {Icon && <Icon size={16} aria-hidden="true" style={{ flexShrink: 0 }} />}
                            {/* A user's name/email can be arbitrarily long - truncate
                                instead of wrapping unevenly against the icon. */}
                            <div className="flex flex-col min-w-0 flex-[1_1_auto]">
                                <AppTooltip content={item.label}>
                                    <p className="font-medium truncate">{item.label}</p>
                                </AppTooltip>
                                {item.sublabel && (
                                    <AppTooltip content={item.sublabel}>
                                        <p className="text-xs text-fg-muted truncate">
                                            {item.sublabel}
                                        </p>
                                    </AppTooltip>
                                )}
                            </div>
                        </button>
                    </React.Fragment>
                );
            })}
        </>
    );
};

export default CommandPaletteResultsList;
