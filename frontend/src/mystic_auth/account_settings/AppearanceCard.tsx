import React, { useEffect, useRef, useState } from "react";
import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import FormAlert from "../ui/feedback/FormAlert";
import { Button } from "../ui/buttons/Button";
import { Input } from "../ui/inputs/Input";
import { Label } from "../ui/shadcn/label";
import { cn } from "../ui/styles/classNames";
import { useUpdateMyAccountMutation } from "./useUpdateMyAccountMutation";
import { toaster } from "../ui/toaster/toasterInstance";
import { useAppearanceStore } from "../store/appearanceStore";
import { generateBrandScale, contrastRatio } from "../theme/generateBrandScale";
import { deriveCanvasFrom } from "../theme/appearanceThemeOverrides";
import { BRAND_COLOR as DEFAULT_BRAND_COLOR } from "../core/settings";

// Quick-pick presets shown under the color input (design/account-settings.html's
// "Suggested (all readable)" swatch row): a curated spread of hues, each
// already passing the same white-text contrast check as a hand-typed hex
// (see brandLowContrast below), so every swatch here is a safe one-click
// pick - every entry here must pass contrastRatio(generateBrandScale(hex)["600"],
// "#ffffff") >= 3, the same check the manual hex field is held to. Stock
// Tailwind teal-600/green-600 fail that (contrast ~2.3-2.6, generateBrandScale
// only carries a swatch's hue/saturation into the 600 step, not its
// lightness, so a vivid teal/green stays too light at l:44% to clear 3:1);
// #2d6876/#2f7448 are hand-desaturated equivalents that pass with margin
// (~3.3-3.7). Not an exhaustive palette - just enough variety (warm default,
// cool blues/violets, a couple of warm accents, and a neutral) to cover most
// tastes without turning this into a full color picker.
const SUGGESTED_BRAND_COLORS = [
    DEFAULT_BRAND_COLOR,
    "#2563eb",
    "#1e40af",
    "#4f46e5",
    "#7c3aed",
    "#a21caf",
    "#db2777",
    "#ea580c",
    "#2d6876",
    "#2f7448",
];

// fg.default's fixed values in tailwind.css: text color doesn't move
// with the derived background, so preview boxes check against these.
const FG_LIGHT = "#3f3f46";
const FG_DARK = "#f4f4f5";
const HEX_RE = /^#[0-9a-fA-F]{6}$/;

// Committing to appearanceStore rewrites the app's CSS variables. Doing that
// on every 'input' tick while dragging the native
// color picker made the drag feel laggy. The swatch/hex field and preview
// still update every tick; only the expensive theme commit is debounced.
const COMMIT_DEBOUNCE_MS = 100;

/**
 * Lets the signed-in user pick a custom brand color. Every pick applies
 * immediately via appearanceStore, which applyBrandCssVars.ts uses to update
 * the CSS variables, so this is the live app, not a separate preview.
 * The page background gradient derives automatically from the same pick
 * (see appearanceThemeOverrides.ts's deriveCanvasFrom). Save persists the
 * color (PUT /users/me) so it follows the user across devices.
 */
const AppearanceCard: React.FC = () => {
    const { t } = useTranslation("account_settings");
    // Selected as an individual primitive, not an object-literal selector:
    // Zustand's useSyncExternalStore compares snapshots by reference, and
    // `(s) => ({...})` returns a new object every render, which never equals
    // the previous one. React treats that as "the store changed" and loops
    // until it throws "Maximum update depth exceeded" (an earlier version of
    // this file had exactly that bug, seen as a blank Appearance tab).
    const storedBrandColor = useAppearanceStore((s) => s.brandColor);
    const setBrandColor = useAppearanceStore((s) => s.setBrandColor);

    const [draftBrand, setDraftBrand] = useState(storedBrandColor ?? DEFAULT_BRAND_COLOR);
    const mutation = useUpdateMyAccountMutation();
    const commitTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => () => {
        if (commitTimer.current) clearTimeout(commitTimer.current);
    }, []);

    const isAtDefault = storedBrandColor == null && draftBrand === DEFAULT_BRAND_COLOR;

    const isBrandValid = HEX_RE.test(draftBrand);
    const scale = isBrandValid ? generateBrandScale(draftBrand) : null;
    const brandLowContrast = scale ? contrastRatio(scale["600"], "#ffffff") < 3 : false;
    const canvasFrom = scale ? deriveCanvasFrom(scale) : null;

    const handleBrandPick = (hex: string) => {
        setDraftBrand(hex);
        if (!HEX_RE.test(hex)) return;

        if (commitTimer.current) clearTimeout(commitTimer.current);
        commitTimer.current = setTimeout(() => setBrandColor(hex), COMMIT_DEBOUNCE_MS);
    };

    const handleSave = () => {
        if (!isBrandValid) return;
        if (commitTimer.current) clearTimeout(commitTimer.current);
        setBrandColor(draftBrand);
        mutation.mutate(
            { brand_color: draftBrand },
            { onSuccess: () => toaster.create({ title: t("appearance.updatedToast"), type: "success" }) }
        );
    };

    const handleReset = () => {
        if (isAtDefault) return;
        if (commitTimer.current) clearTimeout(commitTimer.current);
        setDraftBrand(DEFAULT_BRAND_COLOR);
        setBrandColor(null);
        mutation.mutate(
            { brand_color: null },
            { onSuccess: () => toaster.create({ title: t("appearance.resetToast"), type: "success" }) }
        );
    };

    return (
        <Card className="p-5">
            <SectionHeading className="mb-3">
                {t("appearance.title")}
            </SectionHeading>
            <div className="flex flex-col gap-4">
                <p className="text-fg-muted text-sm">
                    {t("appearance.description")}
                </p>

                <div className="flex items-start flex-wrap gap-4">
                    <div className="flex-1 min-w-48 flex flex-col gap-1.5">
                        <Label htmlFor="appearance-brand-hex">{t("appearance.brandColorLabel")}</Label>
                        <div className="flex items-center gap-3">
                            <Input
                                type="color"
                                aria-label={t("appearance.brandColorLabel")}
                                value={isBrandValid ? draftBrand : DEFAULT_BRAND_COLOR}
                                onChange={(e) => handleBrandPick(e.target.value)}
                                className="p-1 w-14 h-11 cursor-pointer"
                            />
                            <Input
                                id="appearance-brand-hex"
                                value={draftBrand}
                                onChange={(e) => handleBrandPick(e.target.value)}
                                className="max-w-40"
                                aria-invalid={!isBrandValid}
                                size="lg"
                            />
                        </div>

                        <div className="flex flex-col gap-1.5 mt-1">
                            <span className="text-fg-muted text-sm">{t("appearance.suggestedColorsLabel")}</span>
                            <div className="flex flex-wrap gap-2" role="group" aria-label={t("appearance.suggestedColorsLabel")}>
                                {SUGGESTED_BRAND_COLORS.map((hex) => {
                                    const isSelected = isBrandValid && draftBrand.toLowerCase() === hex.toLowerCase();
                                    return (
                                        <button
                                            key={hex}
                                            type="button"
                                            onClick={() => handleBrandPick(hex)}
                                            aria-label={t("appearance.suggestedColorName", { hex })}
                                            aria-pressed={isSelected}
                                            className={cn(
                                                "size-8 rounded-full border-2 transition-all cursor-pointer flex items-center justify-center",
                                                isSelected
                                                    ? "border-fg-default scale-110"
                                                    : "border-transparent hover:scale-110 hover:border-border-strong"
                                            )}
                                            style={{ backgroundColor: hex }}
                                        >
                                            {isSelected && <Check size={16} className="text-white drop-shadow-[0_0_1px_rgba(0,0,0,0.8)]" aria-hidden="true" />}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    {scale && canvasFrom && (
                        <>
                            <div className="flex-1 min-w-40 rounded-md border-2 border-black/30 p-4" style={{ backgroundColor: canvasFrom.light }}>
                                <p className="text-sm mb-2" style={{ color: FG_LIGHT }}>
                                    {t("appearance.previewLight")}
                                </p>
                                <Button style={{ backgroundColor: scale["600"], color: "white" }} size="sm">
                                    {t("appearance.previewButton")}
                                </Button>
                            </div>
                            <div className="flex-1 min-w-40 rounded-md border-2 border-white/30 p-4" style={{ backgroundColor: canvasFrom.dark }}>
                                <p className="text-sm mb-2" style={{ color: FG_DARK }}>
                                    {t("appearance.previewDark")}
                                </p>
                                <Button style={{ backgroundColor: scale["500"], color: "white" }} size="sm">
                                    {t("appearance.previewButton")}
                                </Button>
                            </div>
                        </>
                    )}
                </div>

                {!isBrandValid && <FormAlert size="lg" status="error">Enter a valid hex color, e.g. #b5533c</FormAlert>}

                <div className={cn("min-h-10", isBrandValid && brandLowContrast ? "visible" : "invisible")}>
                    <FormAlert size="md" status="warning">{t("appearance.contrastWarning")}</FormAlert>
                </div>

                {mutation.isError && <FormAlert size="lg" status="error">{mutation.error.message}</FormAlert>}

                <div className="flex items-center gap-3">
                    <Button
                        variant="brand"
                        loading={mutation.isPending}
                        disabled={!isBrandValid}
                        onClick={handleSave}
                    >
                        {t("appearance.saveButton")}
                    </Button>
                    <Button onClick={handleReset} disabled={mutation.isPending || isAtDefault} variant="secondary">
                        {t("appearance.resetButton")}
                    </Button>
                </div>
            </div>
        </Card>
    );
};

export default AppearanceCard;
