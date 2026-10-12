import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useTranslation } from "react-i18next";

import { useLoginMutation } from "./useLoginMutation";
import FormAlert from "../../ui/feedback/FormAlert";
import PasswordInput from "../../ui/inputs/PasswordInput";
import AuthInlineLink from "../../ui/links/AuthInlineLink";
import { Button } from "../../ui/buttons/Button";
import { Input } from "../../ui/inputs/Input";
import { Label } from "../../ui/shadcn/label";
import { useCooldown } from "../../ui/hooks/useCooldown";

interface LoginFormProps {
    onSuccess?: () => void;
    onAttempt?: () => void;
}

// mm:ss for the lockout countdown ("Try again in 14:52"), matching
// design/auth.html. Minutes can exceed 59 (a long lockout), so this isn't
// clamped to a fixed two digits.
function formatMinutesSeconds(totalSeconds: number): string {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, onAttempt }) => {
    const { t } = useTranslation("auth");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    // Seeded from the backend's ACCOUNT_LOCKED response (params.minutes,
    // login_handler.py) so the button's countdown reflects the server's own
    // lockout window instead of a client-guessed value.
    const { cooldown: lockedSeconds, startCooldown: startLockedCooldown } = useCooldown();
    const errorPanelRef = useRef<HTMLDivElement>(null);

    const loginMutation = useLoginMutation();
    const cause = loginMutation.error?.cause;
    const isRetryableError = loginMutation.isError && axios.isAxiosError(cause) &&
        (!cause.response || cause.response.status >= 500);

    useEffect(() => {
        if (loginMutation.isSuccess && onSuccess) {
            onSuccess();
        }
    }, [loginMutation.isSuccess, onSuccess]);

    useEffect(() => {
        if (!loginMutation.isError) return;
        const cause = loginMutation.error.cause;
        if (axios.isAxiosError(cause) && cause.response?.status === 429) {
            const headers = cause.response.headers;
            const retryAfterHeader = typeof headers?.get === "function"
                ? headers.get("retry-after")
                : headers?.["retry-after"] ?? headers?.["Retry-After"];
            const retryAfter = Number(retryAfterHeader);
            if (Number.isFinite(retryAfter) && retryAfter > 0) {
                startLockedCooldown(Math.ceil(retryAfter));
            } else if (cause.response.data?.code === "ACCOUNT_LOCKED") {
                const minutes = Number(cause.response.data?.params?.minutes) || 1;
                startLockedCooldown(minutes * 60);
            }
        }
        // Only re-runs when a new error comes in, not every render: startLockedCooldown's
        // identity is stable (useCooldown), and loginMutation.error changes with isError.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loginMutation.isError, loginMutation.error]);

    useEffect(() => {
        if (loginMutation.isError) {
            errorPanelRef.current?.focus();
        }
    }, [loginMutation.isError, loginMutation.error]);

    const handleSubmit = (e: React.SubmitEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (lockedSeconds > 0) return;
        onAttempt?.();
        loginMutation.mutate({ email, password });
    };

    const isLocked = lockedSeconds > 0;

    return (
        <form onSubmit={handleSubmit} className="w-full flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
                <Label htmlFor="login-email" className="text-base">{t("login.emailLabel")}</Label>
                {/* bg-bg-canvas (not the card's own bg-bg-surface) so fields read as
                    recessed into the card. */}
                <Input
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("login.emailPlaceholder")}
                    autoComplete="email"
                    className="bg-bg-canvas"
                    size="lg"
                    required
                    aria-invalid={loginMutation.isError}
                    aria-describedby={loginMutation.isError ? "login-error" : undefined}
                />
            </div>

            <div className="flex flex-col gap-1.5">
                <div className="flex flex-row justify-between items-baseline w-full">
                    <Label htmlFor="login-password" className="text-base">{t("login.passwordLabel")}</Label>
                    {/* On the password field's own label row, not a separate row below
                        the button: the common spot, and one less row on the card. */}
                    <p className="text-sm">
                        <AuthInlineLink to="/password-reset-request">
                            {t("login.forgotPassword")}
                        </AuthInlineLink>
                    </p>
                </div>
                <PasswordInput
                    id="login-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={t("login.passwordPlaceholder")}
                    autoComplete="current-password"
                    className="bg-bg-canvas"
                    size="lg"
                    required
                    maxLength={128}
                    aria-invalid={loginMutation.isError}
                    aria-describedby={loginMutation.isError ? "login-error" : undefined}
                />
            </div>

            {/* Server errors (wrong password, locked, rate limited) sit directly above
                the main button, so they're in view when the user clicks again.
                errors.json's own ACCOUNT_LOCKED translation already renders the
                minutes-granularity lockout copy, so it's used as-is; only the
                button below adds its own live mm:ss countdown. */}
            {loginMutation.isError && (
                <div ref={errorPanelRef} tabIndex={-1} className="rounded-md outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
                    <FormAlert status="error" id="login-error">
                        {loginMutation.error.message}
                    </FormAlert>
                </div>
            )}

            {loginMutation.isSuccess && (
                <FormAlert status="success">
                    {t("login.loginSuccess")}
                </FormAlert>
            )}

            <Button
                type="submit"
                variant="brand"
                size="lg"
                className="w-full"
                loading={loginMutation.isPending}
                disabled={isLocked}
            >
                {isLocked
                    ? t("login.tryAgainIn", { time: formatMinutesSeconds(lockedSeconds) })
                    : isRetryableError
                        ? t("login.retryButton")
                        : t("login.submitButton")}
            </Button>
        </form>
    );
};

export default LoginForm;
