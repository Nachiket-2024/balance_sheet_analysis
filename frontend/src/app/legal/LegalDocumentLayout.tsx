import React, { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { ArrowLeft } from "lucide-react";

import { Card, AuthLayout, Logo, Button, useAuthStore } from "../sdk";

// Side-effect import: registers the "legal" i18next namespace so both
// PrivacyPolicyPage and TermsOfServicePage's useTranslation("legal") calls
// resolve, regardless of which one is visited first. Lives here (the shell
// both pages render through) so it only needs registering once.
import "../translations/registerLegalTranslations";

export interface LegalSection {
    heading: string;
    paragraphs: string[];
}

interface LegalDocumentLayoutProps {
    title: string;
    lastUpdatedLabel: string;
    lastUpdatedDate: string;
    backLabel: string;
    reviewNote?: string;
    intro: string[];
    sections: LegalSection[];
}

/**
 * Goes back to wherever the visitor actually came from (Sidebar footer for
 * an authenticated user, LoginPage/SignupForm's footnote otherwise) instead
 * of hardcoding "/", which used to send every "Back" click to the landing
 * page even from deep inside the app. `location.key !== "default"` is
 * react-router's signal that this history entry has a predecessor in this
 * browser tab (a fresh/bookmarked load of /privacy or /terms gets the
 * literal string "default"); only then is `navigate(-1)` safe. Otherwise
 * fall back to /dashboard (signed in) or "/" (not signed in).
 */
const BackButton: React.FC<{ label: string }> = ({ label }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    const handleBack = () => {
        if (location.key !== "default") {
            navigate(-1);
        } else {
            navigate(isAuthenticated ? "/dashboard" : "/");
        }
    };

    return (
        <Button variant="brand" size="sm" onClick={handleBack}>
            <ArrowLeft size={16} aria-hidden="true" />
            {label}
        </Button>
    );
};

/**
 * Shared shell for the Privacy Policy and Terms of Service pages: same
 * AuthLayout/Card chrome as the rest of the unauthenticated flow (plus the
 * same Logo so the page doesn't start cold at the document title), just
 * wide enough for comfortable prose instead of the narrow auth-form width.
 *
 * Purely presentational: the caller (PrivacyPolicyPage/TermsOfServicePage)
 * resolves all translated content via the "legal" i18n namespace and passes
 * it in as props, so this component doesn't need to know which document
 * it's rendering.
 */
const LegalDocumentLayout: React.FC<LegalDocumentLayoutProps> = ({
    title,
    lastUpdatedLabel,
    lastUpdatedDate,
    backLabel,
    reviewNote,
    intro,
    sections,
}) => {
    // Reachable via an in-app link (Sidebar's footer) whose page may be
    // scrolled well past the top; without this, navigating here keeps that
    // old scroll position instead of landing at the top of the document.
    useEffect(() => {
        // `document.body`, not the viewport, is this app's actual scrolling
        // element (see globalCss's html/body split in theme/themeStyles.ts).
        // window.scrollTo(0, 0) would be a silent no-op here.
        document.body.scrollTop = 0;
    }, []);

    return (
        <AuthLayout variant="status">
            <Card className="w-full max-w-3xl border-t-[3px] border-t-brand-solid p-5 md:p-8">
                <div className="flex flex-col gap-6">
                    <div className="relative flex items-center justify-center">
                        {/* Default (md) size, not Sidebar's compact "sm": this is the only
                            brand mark on the page, same anchor role Logo plays on
                            LoginPage/SignupPage. */}
                        <Logo />
                        <div className="absolute right-0">
                            <BackButton label={backLabel} />
                        </div>
                    </div>
                    <div className="h-px w-full bg-brand-solid" aria-hidden="true" />

                    <div className="flex flex-col items-start gap-1 text-left">
                        <h1 className="text-brand-fg text-[22px] leading-[1.2] font-bold tracking-[-0.01em]">
                            {title}
                        </h1>
                        <p className="text-sm text-fg-muted">
                            {lastUpdatedLabel}: {lastUpdatedDate}
                        </p>
                    </div>

                    {reviewNote && (
                        <p className="rounded-md border border-brand-solid/40 bg-brand-tile-subtle p-3 text-sm text-fg-default">
                            {reviewNote}
                        </p>
                    )}

                    <div className="flex flex-col gap-3">
                        {intro.map((paragraph) => (
                            <p key={paragraph} className="text-fg-default text-base">
                                {paragraph}
                            </p>
                        ))}
                    </div>

                    {sections.map((section) => (
                        <div key={section.heading} className="flex flex-col gap-2">
                            <h2 className="text-brand-fg text-base font-semibold tracking-[-0.01em]">
                                {section.heading}
                            </h2>
                            {section.paragraphs.map((paragraph) => (
                                <p key={paragraph} className="text-fg-default text-base">
                                    {paragraph}
                                </p>
                            ))}
                        </div>
                    ))}

                    <div className="flex w-full justify-end border-t border-brand-border pt-4">
                        <BackButton label={backLabel} />
                    </div>
                </div>
            </Card>
        </AuthLayout>
    );
};

export default LegalDocumentLayout;
