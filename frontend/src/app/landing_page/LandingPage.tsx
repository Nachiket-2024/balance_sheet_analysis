import React from "react";
import { Navigate, Link as RouterLink } from "react-router";
import { useTranslation } from "react-i18next";
import { ArrowRight, Building2, CheckCircle2, LineChart, MessageCircleQuestion, ShieldCheck } from "lucide-react";

// Everything below comes from the public extension surface (../sdk), not
// internal mystic_auth/* paths. This page is the reference example for an
// app-owned public page outside the authenticated shell.
import {
    useAuthStore,
    APP_NAME,
    SUPPORT_EMAIL,
    Card,
    Logo,
    ControlCluster,
    AuthInlineLink,
    Button,
} from "../sdk";

import "../translations/registerLandingTranslations";

const HIGHLIGHTS = [
    { icon: Building2, key: "companyImport" },
    { icon: LineChart, key: "trends" },
    { icon: MessageCircleQuestion, key: "llmQa" },
    { icon: ShieldCheck, key: "accessControl" },
] as const;

/**
 * LandingPage
 * ----------------------------
 * Pre-auth marketing page: hero, feature-highlight grid, and CTAs into
 * signup/login. Built on mystic-auth's "outside the auth shell" pattern
 * (no AppLayout, no ProtectedRoute) - see
 * docs/mystic_auth/template-usage/overview.md and
 * worked-example.md#6-a-pre-auth-landing-page - with copy customized for
 * this app instead of the template's own.
 *
 * Redirects a signed-in visitor to /dashboard instead of showing marketing
 * copy for a product they're already in, using the same `isAuthenticated`
 * check LoginPage/SignupPage use.
 */
const LandingPage: React.FC = () => {
    const { t } = useTranslation("landing");
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

    if (isAuthenticated) return <Navigate to="/dashboard" replace />;

    return (
        <div className="relative isolate flex min-h-screen flex-col overflow-y-auto bg-bg-canvas bg-linear-to-b from-(--bg-canvas-from) to-(--bg-canvas-to)">
            <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(760px_420px_at_15%_0%,color-mix(in_srgb,var(--brand-solid)_18%,transparent),transparent_68%),radial-gradient(680px_420px_at_92%_24%,color-mix(in_srgb,var(--accent-solid)_12%,transparent),transparent_66%)] dark:bg-[radial-gradient(760px_420px_at_15%_0%,color-mix(in_srgb,var(--brand-solid)_25%,transparent),transparent_68%),radial-gradient(680px_420px_at_92%_24%,color-mix(in_srgb,var(--accent-solid)_14%,transparent),transparent_66%)]" />
            <a
                href="#main-content"
                className="sr-only z-50 rounded-md bg-bg-surface px-3 py-2 text-sm font-semibold text-fg-default shadow-card focus:not-sr-only focus:absolute focus:left-4 focus:top-4"
            >
                {t("skipToContent")}
            </a>

            <header className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-y-2 px-4 py-4 md:px-8 md:py-5">
                <RouterLink
                    to="/"
                    aria-label={t("brandHome", { appName: APP_NAME })}
                    className="shrink-0 rounded-md focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
                >
                    <Logo size="sm" />
                </RouterLink>
                <nav aria-label={t("primaryNavigation")} className="flex flex-wrap items-center justify-end gap-3">
                    <ControlCluster />
                    <Button asChild variant="brand-outline" size="sm">
                        <RouterLink to="/login">{t("logIn")}</RouterLink>
                    </Button>
                    <Button asChild variant="brand" size="sm">
                        <RouterLink to="/signup">{t("signUp")}</RouterLink>
                    </Button>
                </nav>
            </header>

            <main id="main-content" tabIndex={-1} className="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col px-4 pb-8 focus:outline-none md:px-8 md:pb-12">
                <section aria-labelledby="landing-hero-title" className="grid items-center gap-10 pb-10 pt-10 lg:grid-cols-[1.02fr_0.98fr] lg:gap-16 lg:pb-16 lg:pt-16">
                    <div className="max-w-2xl">
                        <h1 id="landing-hero-title" className="mb-5 text-4xl font-bold leading-[1.08] tracking-[-0.035em] sm:text-5xl lg:text-6xl">
                            {t("hero.title")}
                        </h1>
                        <p className="mb-7 max-w-xl text-lg leading-8 text-fg-muted">
                            {t("hero.subtitle", { appName: APP_NAME })}
                        </p>
                        <div className="flex flex-wrap items-center gap-3">
                            <Button asChild variant="brand" size="lg">
                                <RouterLink to="/signup">{t("hero.getStarted")} <ArrowRight aria-hidden="true" /></RouterLink>
                            </Button>
                            <Button asChild variant="brand-outline" size="lg">
                                <RouterLink to="/login">{t("logIn")}</RouterLink>
                            </Button>
                        </div>
                        <div className="mt-7 flex flex-wrap gap-x-5 gap-y-2 text-sm text-fg-muted">
                            {["companyImport", "trends", "accessControl"].map((key) => <span key={key} className="inline-flex items-center gap-1.5"><CheckCircle2 size={15} className="text-brand-fg" aria-hidden="true" />{t(`highlights.${key}.title`)}</span>)}
                        </div>
                    </div>

                    <section aria-labelledby="landing-snapshot-title" className="min-w-0 py-3 sm:py-5">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-fg-muted">{t("snapshot.label")}</p>
                        <h2 id="landing-snapshot-title" className="mt-2 text-xl font-semibold tracking-tight">{t("snapshot.title")}</h2>
                        <div className="mt-7 grid grid-cols-3 gap-3 sm:gap-6">
                            {[{ label: "assets", value: "108.0M", color: "text-brand-fg" }, { label: "liabilities", value: "62.6M", color: "text-orange-700 dark:text-orange-300" }, { label: "equity", value: "45.4M", color: "text-emerald-700 dark:text-emerald-300" }].map((metric) => (
                                <div key={metric.label}>
                                    <p className="text-xs text-fg-muted">{t(`snapshot.${metric.label}`)}</p>
                                    <p className={`mt-2 text-lg font-semibold sm:text-xl ${metric.color}`}>{metric.value}</p>
                                    <p className="mt-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">+8.0%</p>
                                </div>
                            ))}
                        </div>
                        <div className="mt-7">
                            <div className="mb-3 flex items-center justify-between text-xs text-fg-muted"><span>FY 2022</span><span>FY 2023</span></div>
                            <div className="flex h-20 items-end gap-2 sm:h-24">{[34, 42, 48, 55, 62, 70, 78, 86].map((height, index) => <div className="flex-1 rounded-t-sm bg-linear-to-t from-brand-solid/40 to-brand-solid" style={{ height: `${height}%`, opacity: 0.55 + index * 0.06 }} key={height} />)}</div>
                        </div>
                        <RouterLink to="/login" className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-brand-fg hover:underline">{t("snapshot.viewAnalysis")} <ArrowRight size={15} aria-hidden="true" /></RouterLink>
                    </section>
                </section>

                <section aria-labelledby="landing-highlights-title" className="w-full border-t border-border-card pt-8 md:pt-10">
                        <h2 id="landing-highlights-title" className="mb-5 text-center text-xl font-semibold tracking-tight">
                            {t("highlights.heading")}
                    </h2>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {HIGHLIGHTS.map(({ icon: HighlightIcon, key }) => (
                            <Card as="article" key={key} className="group p-5 text-left hover:-translate-y-0.5">
                                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-tile-subtle text-brand-solid transition-colors group-hover:bg-brand-solid group-hover:text-brand-contrast">
                                    <HighlightIcon size={20} aria-hidden="true" />
                                </div>
                                <div className="mb-1 flex items-center gap-2">
                                    <h3 className="font-semibold">
                                        {t(`highlights.${key}.title`)}
                                    </h3>
                                </div>
                                <p className="text-sm text-fg-muted">
                                    {t(`highlights.${key}.description`)}
                                </p>
                            </Card>
                        ))}
                    </div>
                </section>
            </main>

            <footer className="flex justify-center px-4 py-3 md:py-4">
                <nav aria-label={t("footerNavigation")} className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-fg-muted">
                    <AuthInlineLink to="/privacy">{t("footer.privacyPolicy")}</AuthInlineLink>
                    <span aria-hidden="true">·</span>
                    <AuthInlineLink to="/terms">{t("footer.termsOfService")}</AuthInlineLink>
                    {SUPPORT_EMAIL && (
                        <>
                            <span aria-hidden="true">·</span>
                            <a
                                className="font-semibold text-brand-fg no-underline hover:text-[var(--brand-600)] hover:underline"
                                href={`mailto:${SUPPORT_EMAIL}`}
                            >
                                {t("footer.support")}
                            </a>
                        </>
                    )}
                </nav>
            </footer>
        </div>
    );
};

export default LandingPage;
