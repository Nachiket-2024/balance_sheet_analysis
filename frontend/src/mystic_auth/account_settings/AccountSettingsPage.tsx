import React, { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/shadcn/tabs";
import {
    FileText,
    KeyRound,
    Palette,
    Settings,
    ShieldCheck,
    Trash2,
    UserRound,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import PageContainer from "../ui/navigation/PageContainer";
import Card from "../ui/cards/Card";
import SectionHeading from "../ui/navigation/SectionHeading";
import AuthInlineLink from "../ui/links/AuthInlineLink";
import { useAuthStore } from "../store/authStore";
import ProfileNameCard from "./ProfileNameCard";
import ChangePasswordCard from "./ChangePasswordCard";
import AccountStatusCard from "./AccountStatusCard";
import AppearanceCard from "./AppearanceCard";
import DeleteAccountCard from "./DeleteAccountCard";
import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning";
import { useAccountSettingsUiStore } from "./accountSettingsUiStore";

/**
 * Extra tabs an app can append after the built-in ones, same "typed,
 * optional, additive" shape as AppLayout's `extraNavItems`/
 * `extraNavbarContent` (see
     * docs/mystic_auth/template-usage/frontend-customization.md#shared-chrome-extension-points).
 * `value` must be unique among built-in and app-supplied tabs: it's the
 * TabsTrigger/TabsContent pairing key, not just a label.
 */
export interface AccountSettingsExtraTab {
    value: string;
    label: string;
    content: React.ReactNode;
}

interface AccountSettingsPageProps {
    /** Appended after the built-in tabs, in the order given. Optional: omitting
     * it renders just the built-in tabs. */
    extraTabs?: AccountSettingsExtraTab[];
}

const SETTINGS_TAB_CLASSNAME =
    // Match the UserAccessDialog Details/Policies/Permissions strip: the
    // selected tab gets one inset brand outline and tint, while the shared
    // TabsTrigger shadow and dark-mode active border are explicitly replaced
    // so neither can add a second visible edge. Keep the left separator
    // stable while hovering; changing the whole border would animate that
    // separator and create a brief flash while moving between tabs. The min
    // size and desktop flex are intentional for the settings nav's larger
    // touch targets and full-width layout.
    "relative min-h-10 min-w-[8rem] flex-none shrink-0 rounded-none px-3 py-2 text-sm font-semibold cursor-pointer flex items-center justify-center gap-2 whitespace-nowrap transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] before:absolute before:inset-y-0 before:left-0 before:w-px before:bg-border-strong first:before:hidden data-[state=active]:before:hidden !text-fg-muted !bg-transparent hover:!bg-brand-subtle hover:!text-brand-fg data-[state=active]:!border-transparent dark:data-[state=active]:!border-transparent data-[state=active]:!bg-brand-tile-subtle data-[state=active]:!text-brand-fg data-[state=active]:!shadow-[inset_0_0_0_2px_var(--brand-solid)] lg:flex-1";

const DANGER_TAB_CLASSNAME =
    // Unlike SETTINGS_TAB_CLASSNAME, red stays on at rest (!text-red-fg, not
    // !text-fg-muted) - same "red instant logout"-style preference as the
    // rest of the app: a destructive tab reads as destructive immediately,
    // not only once hovered or selected. Its selected outline follows the
    // same UserAccessDialog tab treatment in red.
    "relative min-h-10 min-w-[8rem] flex-none shrink-0 rounded-none px-3 py-2 text-sm font-semibold cursor-pointer flex items-center justify-center gap-2 whitespace-nowrap transition-[background-color,color,box-shadow] duration-[var(--duration-hover)] ease-[var(--easing-hover)] before:absolute before:inset-y-0 before:left-0 before:w-px before:bg-border-strong first:before:hidden data-[state=active]:before:hidden !text-red-fg !bg-transparent hover:!bg-red-subtle data-[state=active]:!border-transparent dark:data-[state=active]:!border-transparent data-[state=active]:!bg-red-subtle data-[state=active]:!shadow-[inset_0_0_0_2px_var(--red-600)] lg:flex-1";

/**
 * AccountSettingsPage (nav label/route: "Account Settings")
 * ----------------------------
 * Self-service account management: rename your own account, change/set your
 * password, and see your own effective policies. Name and password both go
 * through PUT /users/me, via two independent forms/cards below. Doesn't
 * repeat email/role/member-since since DashboardPage already shows those as
 * read-only context. Session management (ActiveSessionsCard) also lives on
 * DashboardPage now, not here - see that page's docstring. No permission
 * required beyond authentication: this is the self-service surface
 * users:read_own/users:update_own exist for.
 *
 * Composes five independent widgets, each its own tab: ProfileNameCard
 * (name), ChangePasswordCard (password, including whether one is set),
 * AccountStatusCard (read-only policy/permission list), a Legal tab
 * (Privacy Policy/Terms of Service links, the only way to reach either once
 * signed in), and DeleteAccountCard (self-service deletion, DELETE
 * /users/me), kept last since it's destructive. This page only owns what has to live
 * above all of them: a combined unsaved-changes warning, since switching
 * tabs shouldn't discard an in-progress edit on another tab. Radix's
 * TabsContent always unmounts an inactive panel unless `forceMount` is
 * set, and `forceMount` alone would render every tab's content up front
 * (defeating the point). So `visitedTabs` tracks which tabs have been
 * opened at least once; a visited tab renders with `forceMount` and is
 * hidden via a `hidden` class instead of being unmounted - mount on
 * first visit, then keep mounted-but-hidden. DeleteAccountCard is
 * excluded from the dirty tracking: its password field isn't an edit worth
 * warning about losing, and its own ConfirmDialog is warning enough already.
 */
const AccountSettingsPage: React.FC<AccountSettingsPageProps> = ({ extraTabs }) => {
    const { t } = useTranslation(["account_settings", "layout"]);
    const name = useAuthStore((s) => s.name);
    const hasPassword = useAuthStore((s) => s.hasPassword);

    const [nameDirty, setNameDirty] = useState(false);
    const [passwordDirty, setPasswordDirty] = useState(false);
    useUnsavedChangesWarning(nameDirty || passwordDirty);

    // Precedence: (1) `?tab=` is a one-shot deep-link override - CommandPalette
    // navigates to e.g. /account-settings?tab=password to land on a specific
    // tab; `key` below forces Tabs to pick up a new `initialTab` on a fresh
    // deep link while leaving normal in-page tab clicks (which don't touch
    // the URL) alone, so manual tab switches still don't lose an
    // in-progress edit. (2) failing that, accountSettingsUiStore remembers
    // the tab last open here across in-app navigation away and back (e.g.
    // Dashboard -> Account Settings should reopen on Appearance, not reset
    // to Profile). (3) "profile" otherwise.
    // `deepLinkTab` (not `initialTab` as a whole) is what the below `key`
    // reacts to. Keying on `initialTab` itself was a bug: initialTab falls
    // back to storedTab, which handleTabChange updates on every tab
    // switch - so every click (or arrow-key move) changed storedTab, which
    // changed initialTab, which changed `key`, remounting the whole Tabs
    // tree on every switch. That threw focus back to <body> mid-navigation
    // (breaking roving-tabindex arrow-key support across the tab strip)
    // and needlessly discarded each TabsContent's forceMount instance.
    // Keying on deepLinkTab alone still remounts for the one case that
    // needs it (a fresh `?tab=` navigation while already mounted) without
    // reacting to storedTab at all.
    const [searchParams] = useSearchParams();
    const deepLinkTab = searchParams.get("tab");
    const storedTab = useAccountSettingsUiStore((s) => s.activeTab);
    const setStoredTab = useAccountSettingsUiStore((s) => s.update);
    const initialTab = deepLinkTab ?? storedTab ?? "profile";

    const [activeTab, setActiveTab] = useState(initialTab);
    const [visitedTabs, setVisitedTabs] = useState<Set<string>>(() => new Set([initialTab]));
    const handleTabChange = (value: string) => {
        setActiveTab(value);
        setStoredTab({ activeTab: value });
        setVisitedTabs((prev) => (prev.has(value) ? prev : new Set(prev).add(value)));
    };
    const hiddenUnless = (value: string) => (activeTab === value ? undefined : "hidden");

    return (
        <PageContainer title={t("pageTitle")} icon={Settings} description={t("pageDescription")}>
            <Tabs key={deepLinkTab} defaultValue={initialTab} onValueChange={handleTabChange}>
                {/* Six built-in tabs (more with extraTabs) don't fit a phone-width
                    viewport at natural size. Without a scroll container, the
                    tab list shrinks each trigger below its own text width instead
                    of wrapping, so labels overlap and become unreadable (same fix
                    as BulkActionToolbar.tsx on the Users page). overflow-x-auto
                    plus shrink-0/whitespace-nowrap on each trigger turns this into
                    a horizontally scrollable strip instead. -mx-4/px-4 cancel out
                    so the strip still lines up with PageContainer's edges.
                    overflow-y-hidden is required alongside overflow-x-auto, not
                    cosmetic: per the CSS overflow spec, setting only one axis to a
                    non-visible value makes the browser compute the other axis as
                    auto too, which showed up as a stray vertical scrollbar next to
                    the tabs even though nothing here overflows vertically.
                    Full-width on lg+ (lg:w-full) is intentional here, unlike
                    the Permissions page's QuickFilterSegment which hugs its
                    content - this strip is the settings nav, not a filter,
                    so it keeps the larger touch targets and full-width
                    layout (lg:flex-1 on each trigger below). */}
                <TabsList
                    variant="default"
                    aria-label={t("tabs.ariaLabel")}
                    // !h-auto (not h-auto): tabsListVariants' own
                    // group-data-[orientation=horizontal]/tabs:h-9 beats a
                    // plain h-auto, fixing this container at 36px against
                    // each trigger's 40px min-h-10 - the 2px of trigger
                    // clipped off top and bottom by overflow-y-hidden could
                    // cut off the trigger-level active outline, so the
                    // explicit inset outline matches the strip's visible
                    // bounds instead of relying on the shared tab shadow.
                    className="-mx-4 !h-auto w-[calc(100%+2rem)] flex-nowrap justify-start overflow-x-auto overflow-y-hidden rounded-lg border border-border-strong bg-bg-surface p-0 lg:mx-0 lg:w-full"
                >
                    <TabsTrigger value="profile" className={SETTINGS_TAB_CLASSNAME}><UserRound size={15} aria-hidden="true" />{t("tabs.profile")}</TabsTrigger>
                    <TabsTrigger value="password" className={SETTINGS_TAB_CLASSNAME}><KeyRound size={15} aria-hidden="true" />{t("tabs.password")}</TabsTrigger>
                    <TabsTrigger value="status" className={SETTINGS_TAB_CLASSNAME}><ShieldCheck size={15} aria-hidden="true" />{t("tabs.status")}</TabsTrigger>
                    <TabsTrigger value="appearance" className={SETTINGS_TAB_CLASSNAME}><Palette size={15} aria-hidden="true" />{t("tabs.appearance")}</TabsTrigger>
                    <TabsTrigger value="legal" className={SETTINGS_TAB_CLASSNAME}><FileText size={15} aria-hidden="true" />{t("tabs.legal")}</TabsTrigger>
                    <TabsTrigger
                        value="danger"
                        tone="destructive"
                        className={DANGER_TAB_CLASSNAME}
                    >
                        <Trash2 size={15} aria-hidden="true" />
                        {t("tabs.danger")}
                    </TabsTrigger>
                    {extraTabs?.map((tab) => (
                        <TabsTrigger key={tab.value} value={tab.value} className={SETTINGS_TAB_CLASSNAME}>
                            {tab.label}
                        </TabsTrigger>
                    ))}
                </TabsList>

                {visitedTabs.has("profile") && (
                    <TabsContent value="profile" forceMount className={hiddenUnless("profile")}>
                        <div className="max-w-2xl">
                            <ProfileNameCard name={name} onDirtyChange={setNameDirty} />
                        </div>
                    </TabsContent>
                )}

                {visitedTabs.has("password") && (
                    <TabsContent value="password" forceMount className={hiddenUnless("password")}>
                        <div className="max-w-3xl">
                            <ChangePasswordCard hasPassword={hasPassword} onDirtyChange={setPasswordDirty} />
                        </div>
                    </TabsContent>
                )}

                {visitedTabs.has("status") && (
                    <TabsContent value="status" forceMount className={hiddenUnless("status")}>
                        {/* Unlike the other tabs, this one keeps the page's full width
                            (same as Users/Policies): the right column's
                            effective-permissions badge list is open-ended and often the
                            longest thing on the page, so it gets all the width
                            PageContainer's maxW="page.content" allows. See
                            AccountStatusCard's docstring for its own column split. */}
                        <AccountStatusCard />
                    </TabsContent>
                )}

                {visitedTabs.has("appearance") && (
                    <TabsContent value="appearance" forceMount className={hiddenUnless("appearance")}>
                        <div className="max-w-3xl">
                            <AppearanceCard />
                        </div>
                    </TabsContent>
                )}

                {/* Its own tab (not a page footer) so it reads as another
                    self-contained settings section, reachable without leaving the
                    tab strip. Ordered before Danger Zone so the destructive
                    action stays last. */}
                {visitedTabs.has("legal") && (
                    <TabsContent value="legal" forceMount className={hiddenUnless("legal")}>
                        <div className="max-w-2xl">
                            <Card className="p-5">
                                <SectionHeading className="mb-3">
                                    {t("tabs.legal")}
                                </SectionHeading>
                                <div className="flex items-center gap-2">
                                    <AuthInlineLink to="/privacy" className="text-sm">
                                        {t("footer.privacyPolicy", { ns: "layout" })}
                                    </AuthInlineLink>
                                    <p className="text-sm text-fg-muted">
                                        &middot;
                                    </p>
                                    <AuthInlineLink to="/terms" className="text-sm">
                                        {t("footer.termsOfService", { ns: "layout" })}
                                    </AuthInlineLink>
                                </div>
                            </Card>
                        </div>
                    </TabsContent>
                )}

                {visitedTabs.has("danger") && (
                    <TabsContent value="danger" forceMount className={hiddenUnless("danger")}>
                        <div className="max-w-2xl">
                            <DeleteAccountCard hasPassword={hasPassword} />
                        </div>
                    </TabsContent>
                )}

                {extraTabs?.map((tab) =>
                    visitedTabs.has(tab.value) ? (
                        <TabsContent key={tab.value} value={tab.value} forceMount className={hiddenUnless(tab.value)}>
                            {tab.content}
                        </TabsContent>
                    ) : null
                )}
            </Tabs>
        </PageContainer>
    );
};

export default AccountSettingsPage;
