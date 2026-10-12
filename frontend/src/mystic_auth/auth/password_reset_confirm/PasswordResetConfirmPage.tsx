import React from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";

import PasswordResetConfirmForm from "./PasswordResetConfirmForm";

import Card from "../../ui/cards/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";

const PasswordResetConfirmPage: React.FC = () => {
    const { t } = useTranslation("auth");
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const navigate = useNavigate();
    // Keep the one-time token in component memory, then remove it from the
    // address bar/history. The email link still works after initial load,
    // while copied URLs and screenshots no longer retain it.
    const [token] = React.useState(() => {
        const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
        return hashParams.get("token") || searchParams.get("token") || "";
    });

    React.useEffect(() => {
        if (token) navigate("/reset-password", { replace: true });
    }, [navigate, token]);

    return (
        <AuthLayout>
            {/* Same shared width/padding/top-border as every other auth card
                (S1/S7). Was maxW="3xl" - twice as wide as Login/Signup for no
                reason, since this form is a single column either way. */}
            <Card className="mx-auto w-full max-w-md border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center text-center gap-4">
                    <Link to="/">
                        <Logo />
                    </Link>
                    <div className="h-px w-full bg-brand-solid" aria-hidden="true" />
                    <div className="flex flex-col gap-1 mb-1">
                        <h1 className="text-lg font-semibold">{t("passwordResetConfirmPage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {t("passwordResetConfirmPage.subtitle")}
                        </p>
                    </div>

                    <PasswordResetConfirmForm token={token} />
                </div>
            </Card>
        </AuthLayout>
    );
};

export default PasswordResetConfirmPage;
