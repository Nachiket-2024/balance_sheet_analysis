import React from "react";
import { useSearchParams, useNavigate, Link, useLocation } from "react-router";
import { useTranslation } from "react-i18next";

import { Separator } from "../../ui/shadcn/separator";

import ConfirmDeleteAccountButton from "./ConfirmDeleteAccountButton";

// Shared surface styling (theme surface/border tokens), same as every other
// unauthenticated confirmation page (VerifyAccountPage, PasswordResetConfirmPage).
import Card from "../../ui/cards/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";

// Unauthenticated by design (same trust model as PasswordResetConfirmPage/
// VerifyAccountPage): reached via the link in the OAuth-only account deletion
// email (see DeleteAccountCard.tsx / decisions.md#account-lifecycle), which
// must work from any device/browser, not just the one that requested the
// deletion.
const ConfirmDeleteAccountPage: React.FC = () => {
    const { t } = useTranslation("account_settings");
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const navigate = useNavigate();

    // Keep the one-time token in component memory, then remove it from the
    // address bar/history so the destructive link is not retained in copied
    // URLs or screenshots.
    const [token] = React.useState(() => {
        const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
        return hashParams.get("token") || searchParams.get("token") || "";
    });

    React.useEffect(() => {
        if (token) navigate("/confirm-delete", { replace: true });
    }, [navigate, token]);

    const handleSuccessRedirect = () => {
        navigate("/login", { replace: true });
    };

    return (
        <AuthLayout variant="status">
            {/* S1/S7: same shared width/padding/top-border as every other auth
                card (login/signup/reset), not the old md-but-no-accent card. */}
            <Card className="mx-auto w-full max-w-md border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center gap-4 text-center">
                    <Link to="/" aria-label="Return to home">
                        <Logo />
                    </Link>
                    <Separator className="w-full bg-brand-solid" />
                    <div className="mb-1 flex flex-col gap-1">
                        <h1 className="text-lg font-semibold">{t("confirmDeletePage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {t("confirmDeletePage.subtitle")}
                        </p>
                    </div>
                    <ConfirmDeleteAccountButton token={token} onSuccess={handleSuccessRedirect} />
                </div>
            </Card>
        </AuthLayout>
    );
};

export default ConfirmDeleteAccountPage;
