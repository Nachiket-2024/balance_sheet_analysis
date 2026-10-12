import React, { useState } from "react";
import { Link, useNavigate, useLocation, Navigate } from "react-router";
import { useTranslation } from "react-i18next";

import { Separator } from "../../ui/shadcn/separator";

import LoginForm from "./LoginForm";
import OAuth2Button from "../oauth2/OAuth2LoginButton";
import { useAuthStore } from "../../store/authStore";
import AuthInlineLink from "../../ui/links/AuthInlineLink";
import FormAlert from "../../ui/feedback/FormAlert";

import Card from "../../ui/cards/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";


// Reads isAuthenticated from the Zustand auth store (source of truth regardless of
// login method) rather than a per-method loading flag, which used to unmount
// LoginForm mid-typing on unrelated session-check requests.
const LoginPage: React.FC = () => {
    const { t } = useTranslation("auth");
    const navigate = useNavigate();
    const location = useLocation();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    // V3: VerifyAccountPage redirects here with this flag on a successful
    // verification, since a silent redirect gives no sign it worked.
    // Cleared on the next submit attempt, not on a timer, so it survives
    // typing but doesn't linger through a fresh login attempt.
    const [showVerifiedBanner, setShowVerifiedBanner] = useState(
        () => (location.state as { verified?: boolean } | null)?.verified ?? false
    );

    // Always /dashboard, never "wherever the caller was before": a fresh login should
    // be a clean start, not a bounce back to whatever page a session died on.
    if (isAuthenticated) return <Navigate to="/dashboard" replace />;

    const handleLoginSuccess = () => {
        navigate("/dashboard", { replace: true });
    };

    // No page-level error banner here: LoginForm and OAuth2Button each
    // surface their own mutation errors, so a shared banner would either
    // duplicate one of them or never fire. The verified banner above is the
    // one deliberate exception (login itself has no bearing on it).
    return (
        <AuthLayout>
            {/* borderTopWidth/Color: same brand-accent treatment as the dashboard's
                cards (DashboardPage.tsx), so the card reads as the product's own
                even before sign-in. */}
            <Card className="mx-auto w-full max-w-md border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center text-center gap-4">
                    <Link to="/" aria-label="Mystic Auth home">
                        <Logo />
                    </Link>
                    <Separator className="w-full bg-brand-solid" />
                    <div className="flex flex-col gap-1 mb-1">
                        <h1 className="text-lg font-semibold">{t("loginPage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {t("loginPage.subtitle")}
                        </p>
                    </div>

                    {showVerifiedBanner && (
                        <FormAlert status="success">{t("loginPage.emailVerified")}</FormAlert>
                    )}

                    <LoginForm onSuccess={handleLoginSuccess} onAttempt={() => setShowVerifiedBanner(false)} />

                    {/* One divider on this card, between the two ways to log in,
                        not one under every row. */}
                    <div className="flex items-center w-full gap-3">
                        <Separator className="flex-1 w-auto" />
                        <p className="text-xs font-semibold text-fg-muted uppercase tracking-wide">
                            {t("loginPage.or")}
                        </p>
                        <Separator className="flex-1 w-auto" />
                    </div>

                    <OAuth2Button onSuccess={handleLoginSuccess} />

                    <p className="text-base text-fg-muted">
                        {t("loginPage.noAccount")}{" "}
                        <AuthInlineLink to="/signup">
                            {t("loginPage.signUp")}
                        </AuthInlineLink>
                    </p>

                    {/* Same terms footnote as SignupForm's: login accepts the current
                        terms too, and this is the only place a visitor who isn't
                        signing up can reach either document. */}
                    <p className="text-sm text-fg-muted border-t border-border-default pt-3 w-full">
                        {t("loginPage.agreeToTermsPrefix")}{" "}
                        <AuthInlineLink to="/terms">{t("loginPage.termsOfService")}</AuthInlineLink>{" "}
                        {t("loginPage.and")}{" "}
                        <AuthInlineLink to="/privacy">{t("loginPage.privacyPolicy")}</AuthInlineLink>
                    </p>
                </div>
            </Card>
        </AuthLayout>
    );
};

export default LoginPage;
