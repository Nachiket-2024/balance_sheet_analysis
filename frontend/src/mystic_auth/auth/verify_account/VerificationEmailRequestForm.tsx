import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Send } from "lucide-react";

import { useVerificationEmailRequestMutation } from "./useVerificationEmailRequestMutation";
import { useCooldown } from "../../ui/hooks/useCooldown";
import FormAlert from "../../ui/feedback/FormAlert";
import { Button } from "../../ui/buttons/Button";
import { Input } from "../../ui/inputs/Input";
import { Label } from "../../ui/shadcn/label";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

interface VerificationEmailRequestFormProps {
    initialEmail?: string;
    /** V2: true right after a verify attempt failed, so this section (the
     * obvious next step at that point) gets focus instead of the user
     * having to notice it below a disabled Verify button. */
    autoFocus?: boolean;
}

const VerificationEmailRequestForm: React.FC<VerificationEmailRequestFormProps> = ({ initialEmail = "", autoFocus = false }) => {
    const { t } = useTranslation("auth");
    // chromeLanguage, not pageLanguage: numerals stay in English/ASCII digits even in
    // a mixed "en+hi" mode (same as dates); only translated text switches with pageLanguage.
    const language = useLanguageStore((s) => s.chromeLanguage);
    const [email, setEmail] = useState(initialEmail);
    const { cooldown, startCooldown } = useCooldown();
    const requestMutation = useVerificationEmailRequestMutation();
    const emailInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (autoFocus) emailInputRef.current?.focus();
    }, [autoFocus]);

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (cooldown > 0) {
            return;
        }

        // Cooldown follows the server's answer, not the click (same fix as
        // PasswordResetRequestForm.tsx): otherwise a 429 shows "Try again in
        // 60s" on the button while the alert says "Please try again later".
        requestMutation.mutate({ email }, { onSuccess: () => startCooldown() });
    };

    const isCoolingDown = cooldown > 0;

    return (
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
                <Label htmlFor="verify-email-request-email" className="text-base">{t("verifyEmailRequest.emailLabel")}</Label>
                <Input
                    id="verify-email-request-email"
                    ref={emailInputRef}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("verifyEmailRequest.emailPlaceholder")}
                    className="bg-bg-canvas"
                    size="lg"
                    disabled={requestMutation.isPending}
                />
            </div>

            <Button
                type="submit"
                // V4: once cooling down, this shows countdown text rather than
                // an action - the plain outline's disabled/gray look reads
                // clearly in both themes, unlike brand-tinted text at reduced
                // opacity.
                variant={isCoolingDown ? "outline" : "brand-outline"}
                size="lg"
                className="w-full"
                loading={requestMutation.isPending}
                disabled={isCoolingDown || requestMutation.isPending}
            >
                {!isCoolingDown && <Send size={16} style={{ marginRight: 8 }} />}
                {isCoolingDown ? t("verifyEmailRequest.tryAgainIn", { seconds: formatNumber(cooldown, language) }) : t("verifyEmailRequest.submitButton")}
            </Button>

            {requestMutation.isError && (
                <FormAlert status="error">{requestMutation.error.message}</FormAlert>
            )}

            {requestMutation.isSuccess && (
                <FormAlert status="success">{requestMutation.data.message}</FormAlert>
            )}
        </form>
    );
};

export default VerificationEmailRequestForm;
