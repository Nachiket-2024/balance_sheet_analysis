import React, { useState } from "react";
import { Link, useSearchParams, useNavigate, useLocation } from "react-router";
import { useTranslation } from "react-i18next";

import { Separator } from "../../ui/shadcn/separator";

import VerifyAccountButton from "./VerifyAccountButton";
import VerificationEmailRequestForm from "./VerificationEmailRequestForm";
import FormAlert from "../../ui/feedback/FormAlert";
import AuthInlineLink from "../../ui/links/AuthInlineLink";

import Card from "../../ui/cards/Card";

// Shared brand header + footer shell for every unauthenticated page.
import AuthLayout from "../../layout/auth_layout/AuthLayout";
import Logo from "../../layout/app_layout/Logo";

const VerifyAccountPage: React.FC = () => {
    const { t } = useTranslation("auth");
    const [searchParams] = useSearchParams();
    const location = useLocation();
    const navigate = useNavigate();
    // V2: focuses the resend form once a verify attempt fails - at that
    // point retrying the same link can only fail the same way again, so the
    // resend section is the obvious next step.
    const [verifyFailed, setVerifyFailed] = useState(false);

    // Keep the one-time token in component memory, then remove it from the
    // address bar/history while preserving the optional email hint.
    const [token] = useState(() => {
        const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
        return hashParams.get("token") || searchParams.get("token") || "";
    });
    const [email] = useState(() => {
        const hashParams = new URLSearchParams(location.hash.replace(/^#/, ""));
        return hashParams.get("email") || searchParams.get("email") || "";
    });

    React.useEffect(() => {
        if (!token) return;
        navigate("/verify-account", { replace: true });
    }, [email, navigate, token]);

    const handleSuccessRedirect = () => {
        // V3: shown as a success banner on the login card, cleared on its
        // next submit - not a silent redirect that leaves the user unsure
        // whether verifying actually worked.
        navigate("/login", { replace: true, state: { verified: true } });
    };

    return (
        <AuthLayout variant="status">
            {/* Same shared width/padding/top-border as every other auth card
                (S1/S7: Login, Signup, Forgot/Reset Password). */}
            <Card className="mx-auto w-full max-w-md border-t-[3px] border-t-brand-solid bg-bg-surface/95 p-5 shadow-dialog backdrop-blur md:p-7">
                <div className="flex flex-col items-center text-center gap-4">
                    <Link to="/">
                        <Logo />
                    </Link>
                    <Separator className="w-full bg-brand-solid" />
                    <div className="flex flex-col gap-1 mb-1">
                        <h1 className="text-lg font-semibold">{t("verifyAccountPage.heading")}</h1>
                        <p className="text-sm text-fg-muted">
                            {email ? t("verifyAccountPage.subtitleWithEmail", { email }) : t("verifyAccountPage.subtitle")}
                        </p>
                    </div>

                    {/* V1 (bug 2): no token means there's nothing to submit -
                        the button below shows disabled, and this hint is the
                        page's only content pointing at what to do instead. */}
                    {!token && (
                        <FormAlert status="warning">{t("verifyAccountPage.noTokenHint")}</FormAlert>
                    )}

                    <VerifyAccountButton
                        token={token}
                        email={email}
                        onSuccess={handleSuccessRedirect}
                        onError={() => setVerifyFailed(true)}
                    />

                    <div className="flex items-center w-full gap-3">
                        <Separator className="flex-1 w-auto" />
                        <p className="text-xs font-semibold text-fg-muted uppercase tracking-wide">
                            {t("verifyAccountPage.didntGetEmail")}
                        </p>
                        <Separator className="flex-1 w-auto" />
                    </div>

                    <VerificationEmailRequestForm initialEmail={email} autoFocus={verifyFailed} />

                    <p className="text-base text-fg-muted">
                        {t("verifyAccountPage.wrongAccount")}{" "}
                        <AuthInlineLink to="/login">{t("signup.login")}</AuthInlineLink>{" "}
                        {t("loginPage.or")}{" "}
                        <AuthInlineLink to="/signup">{t("loginPage.signUp")}</AuthInlineLink>
                    </p>

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

export default VerifyAccountPage;
