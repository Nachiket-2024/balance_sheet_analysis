import React from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";

import { Separator } from "../../ui/shadcn/separator";

import SignupForm from "./SignupForm";
import OAuth2Button from "../oauth2/OAuth2LoginButton";
import { useAuthStore } from "../../store/authStore";
import AuthInlineLink from "../../ui/links/AuthInlineLink";

import Card from "../../ui/cards/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";

// Same shared width as LoginPage (S1: one card width everywhere so moving
// between login/signup/reset doesn't jump the layout).
const SignupPage: React.FC = () => {
    const { t } = useTranslation("auth");
    const navigate = useNavigate();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    if (isAuthenticated) return <Navigate to="/dashboard" replace />;

    const handleOAuthSuccess = () => {
        navigate("/dashboard", { replace: true });
    };

    return (
        <AuthLayout>
            <Card className="mx-auto w-full max-w-2xl border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center text-center gap-4">
                    <Link to="/">
                        <Logo />
                    </Link>
                    <Separator className="w-full bg-brand-solid" />
                    <div className="flex flex-col gap-1 mb-1">
                        <h1 className="text-lg font-semibold">{t("signupPage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {t("signupPage.subtitle")}
                        </p>
                    </div>

                    <SignupForm />

                    <p className="text-sm text-fg-muted text-center">
                        {t("signup.agreeToTermsPrefix")}{" "}
                        <AuthInlineLink to="/terms">{t("signup.termsOfService")}</AuthInlineLink>{" "}
                        {t("signup.and")}{" "}
                        <AuthInlineLink to="/privacy">{t("signup.privacyPolicy")}</AuthInlineLink>
                    </p>

                    <div className="flex items-center w-full gap-3">
                        <Separator className="flex-1 w-auto" />
                        <p className="text-xs font-semibold text-fg-muted uppercase tracking-wide">
                            {t("loginPage.or")}
                        </p>
                        <Separator className="flex-1 w-auto" />
                    </div>

                    <OAuth2Button onSuccess={handleOAuthSuccess} label={t("oauth2.continueWithGoogle")} />

                    <p className="text-sm text-fg-muted">
                        {t("signup.alreadyHaveAccount")}{" "}
                        <AuthInlineLink to="/login">{t("signup.login")}</AuthInlineLink>
                    </p>
                </div>
            </Card>
        </AuthLayout>
    );
};

export default SignupPage;
