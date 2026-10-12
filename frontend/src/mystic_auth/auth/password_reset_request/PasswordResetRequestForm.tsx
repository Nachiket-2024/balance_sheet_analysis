import React from "react";
import { useTranslation } from "react-i18next";
import { MailCheck } from "lucide-react";

import { usePasswordResetRequestMutation } from "./usePasswordResetRequestMutation";
import { useCooldown } from "../../ui/hooks/useCooldown";
import FormAlert from "../../ui/feedback/FormAlert";
import AuthResultPanel from "../../ui/feedback/AuthResultPanel";
import { Button } from "../../ui/buttons/Button";
import { Input } from "../../ui/inputs/Input";
import { Label } from "../../ui/shadcn/label";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

const PasswordResetRequestForm: React.FC = () => {
    const { t } = useTranslation("auth");
    // chromeLanguage, not pageLanguage: numerals stay in English/ASCII digits even in
    // a mixed "en+hi" mode (same as dates); only translated text switches with pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const [email, setEmail] = React.useState("");
    const { cooldown, startCooldown } = useCooldown();

    const resetRequestMutation = usePasswordResetRequestMutation();

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (cooldown > 0) {
            return;
        }

        // Cooldown follows the server's answer, not the click: starting it
        // immediately made a 429 show "Try again in 60s" on the button next to
        // "Please try again later" in the alert, contradicting each other (F3).
        resetRequestMutation.mutate({ email }, { onSuccess: () => startCooldown() });
    };

    const isCoolingDown = cooldown > 0;

    // F2: success replaces the form with a result panel (mail icon, the
    // server's own "if this email exists..." message so the copy never
    // claims more than the backend actually reports) instead of a green
    // alert sitting above a still-editable form.
    if (resetRequestMutation.isSuccess) {
        return (
            <AuthResultPanel
                icon={<MailCheck size={26} />}
                variant="brand"
                title={t("passwordResetRequest.successTitle")}
                description={resetRequestMutation.data.message}
            >
                <Button
                    variant={isCoolingDown ? "outline" : "brand-outline"}
                    size="lg"
                    className="w-full"
                    disabled={isCoolingDown}
                    onClick={() => resetRequestMutation.mutate({ email }, { onSuccess: () => startCooldown() })}
                >
                    {isCoolingDown
                        ? t("passwordResetRequest.resendIn", { seconds: formatNumber(cooldown, language) })
                        : t("passwordResetRequest.resend")}
                </Button>
            </AuthResultPanel>
        );
    }

    return (
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
                <Label htmlFor="password-reset-request-email" className="text-base">{t("passwordResetRequest.emailLabel")}</Label>
                <Input
                    id="password-reset-request-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("passwordResetRequest.emailPlaceholder")}
                    autoComplete="email"
                    className="bg-bg-canvas"
                    size="lg"
                    autoFocus
                    disabled={resetRequestMutation.isPending}
                />
            </div>

            {/* Server errors (rate limited) sit directly above the main
                button (S6), not a separate alert further down. */}
            {resetRequestMutation.isError && (
                <FormAlert status="error">{resetRequestMutation.error.message}</FormAlert>
            )}

            <Button
                type="submit"
                variant="brand"
                size="lg"
                className="w-full"
                loading={resetRequestMutation.isPending}
                disabled={isCoolingDown || resetRequestMutation.isPending}
            >
                {isCoolingDown ? t("passwordResetRequest.tryAgainIn", { seconds: formatNumber(cooldown, language) }) : t("passwordResetRequest.submitButton")}
            </Button>
        </form>
    );
};

export default PasswordResetRequestForm;
