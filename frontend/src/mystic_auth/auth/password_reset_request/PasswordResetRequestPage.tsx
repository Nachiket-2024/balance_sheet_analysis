import React from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";

import PasswordResetRequestForm from "./PasswordResetRequestForm";

import Card from "../../ui/cards/Card";
import AuthInlineLink from "../../ui/links/AuthInlineLink";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";

const PasswordResetRequestPage: React.FC = () => {
    const { t } = useTranslation("auth");

    return (
        <AuthLayout>
            {/* Same shared width/padding/top-border as every other auth card
                (S1/S7: Login, Signup, Verify Account). */}
            <Card className="mx-auto w-full max-w-md border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center text-center gap-4">
                    <Link to="/">
                        <Logo />
                    </Link>
                    <div className="h-px w-full bg-brand-solid" aria-hidden="true" />
                    <div className="flex flex-col gap-1 mb-1">
                        <h1 className="text-lg font-semibold">{t("passwordResetRequestPage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {t("passwordResetRequestPage.subtitle")}
                        </p>
                    </div>

                    <PasswordResetRequestForm />

                    <p className="text-base text-fg-muted">
                        {t("passwordResetRequestPage.rememberPassword")}{" "}
                        <AuthInlineLink to="/login">
                            {t("passwordResetRequestPage.backToLogin")}
                        </AuthInlineLink>
                    </p>
                </div>
            </Card>
        </AuthLayout>
    );
};

export default PasswordResetRequestPage;
