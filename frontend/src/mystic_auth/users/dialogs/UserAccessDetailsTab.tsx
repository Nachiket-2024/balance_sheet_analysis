import React from "react";
import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  History,
  Key,
  LockKeyhole,
  Shield,
  User as UserIcon,
} from "lucide-react";

import Badge from "../../ui/badges/Badge";
import Card from "../../ui/cards/Card";
import LoadingState from "../../ui/feedback/LoadingState";
import { Button } from "../../ui/buttons/Button";
import { TabsContent } from "../../ui/shadcn/tabs";
import { cn } from "../../ui/styles/classNames";
import {
  formatDateTime,
  formatRelativeTime,
} from "../../ui/dates/dateFormatters";
import { useAllSecurityLogUiStore } from "../../audit_log/security_log/securityLogUiStore";
import type { SupportedLanguage } from "../../translations/translations";
import type { ManagedUserRead } from "../../api/users_api";
import { accessChangeLabel, InfoRow, StatTile, type Translate, type UserAccessState } from "./UserAccessDialogAtoms";

// Details tab of the User Access dialog: role/status/created info plus the
// "Recent access changes" list. Policies and Permissions tabs live in their
// own sibling files, composed together by UserAccessTabs.tsx - split out of
// one 540-line file, see AGENTS.md's ~350-line target.

interface UserAccessDetailsTabProps {
  user: ManagedUserRead;
  state: UserAccessState;
  language: SupportedLanguage;
  totalGranted: number;
  t: Translate;
  navigate: (to: string) => void;
  onTabChange: (tab: "details" | "policies" | "permissions") => void;
}

const UserAccessDetailsTab: React.FC<UserAccessDetailsTabProps> = ({
  user,
  state,
  language,
  totalGranted,
  t,
  navigate,
  onTabChange,
}) => (
  <TabsContent
    id="user-access-tabpanel-details"
    value="details"
    forceMount
    className={cn(
      "flex flex-col min-h-0 flex-1",
      state.tab !== "details" && "hidden",
    )}
  >
    <div className="flex flex-col gap-3 mt-2 flex-1 min-h-0 overflow-y-auto pb-1 [scrollbar-gutter:stable]">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatTile
          icon={<Shield size={21} />}
          num={state.assignedPolicies.length}
          label={t("users:accessDialog.statPolicies")}
          onClick={() => onTabChange("policies")}
          ariaLabel={t("users:accessDialog.viewPolicies", {
            count: state.assignedPolicies.length,
          })}
        />
        <StatTile
          icon={<Key size={21} />}
          num={totalGranted}
          label={t("users:accessDialog.statPermissions")}
          onClick={() => onTabChange("permissions")}
          ariaLabel={t("users:accessDialog.viewPermissions", {
            count: totalGranted,
          })}
        />
        <StatTile
          icon={<UserIcon size={21} />}
          num={state.directGrants.length}
          label={t("users:accessDialog.statGivenDirectly")}
          ariaLabel={t("users:accessDialog.givenDirectlyStat", {
            count: state.directGrants.length,
          })}
        />
      </div>
      <div className="border-t border-border-card pt-3">
        <p className="mb-2 text-base font-semibold">
          {t("users:accessDialog.tabDetails")}
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <InfoRow
            icon={<Shield size={20} />}
            label={t("users:detailsDialog.role")}
          >
            <Badge
              colorPalette="brand"
              variant="subtle"
              size="sm"
              className="capitalize"
            >
              {user.role ?? t("users:detailsDialog.noRoleAssigned")}
            </Badge>
          </InfoRow>
          <InfoRow
            icon={<CheckCircle2 size={20} />}
            label={t("users:detailsDialog.status")}
          >
            <div className="flex flex-wrap items-center gap-1.5">
              {user.is_verified ? (
                <span className="text-sm font-medium text-fg-default">
                  {t("users:detailsDialog.verified")}
                </span>
              ) : (
                <Badge colorPalette="yellow" variant="subtle" size="sm">
                  {t("users:detailsDialog.unverified")}
                </Badge>
              )}
              {!user.is_active && (
                <Badge colorPalette="red" variant="subtle" size="sm">
                  {t("users:detailsDialog.deactivated")}
                </Badge>
              )}
            </div>
          </InfoRow>
          <InfoRow
            icon={<LockKeyhole size={20} />}
            label={t("users:detailsDialog.signsInWith")}
          >
            <Badge colorPalette="gray" variant="subtle" size="sm">
              {user.has_password
                ? t("users:detailsDialog.hasPassword")
                : t("users:detailsDialog.oauthOnly")}
            </Badge>
          </InfoRow>
          <InfoRow
            icon={<CalendarDays size={20} />}
            label={t("users:detailsDialog.created")}
          >
            {formatDateTime(user.created_at, language)}
          </InfoRow>
          <InfoRow
            icon={<Clock3 size={20} />}
            label={t("users:detailsDialog.lastUpdated")}
          >
            {formatDateTime(user.updated_at, language)}
          </InfoRow>
        </div>
      </div>
      {(state.isSelf || state.canReadSecurityAudit) && (
        <div className="flex flex-col gap-2 mt-1">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold uppercase tracking-wide text-fg-muted">
              {t("users:accessDialog.recentAccessChanges")}
            </p>
            <Button
              size="2xs"
              variant="ghost"
              onClick={() => {
                useAllSecurityLogUiStore
                  .getState()
                  .update({ search: user.email });
                navigate("/audit-log?category=security&scope=all");
              }}
            >
              {t("users:accessDialog.viewAllChanges")}
            </Button>
          </div>
          {state.recentAccessChangesQuery.isLoading ? (
            <LoadingState message={t("ui_text:loading")} />
          ) : state.recentAccessChangesQuery.isError ? (
            <p className="text-sm text-fg-muted">
              {t("users:accessDialog.recentAccessChangesFailed")}
            </p>
          ) : !state.recentAccessChangesQuery.data?.length ? (
            <p className="text-sm text-fg-muted">
              {t("users:accessDialog.noRecentAccessChanges")}
            </p>
          ) : (
            <Card className="p-0 overflow-hidden">
              {state.recentAccessChangesQuery.data.map((entry, index) => (
                <div
                  key={entry.id}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5",
                    index > 0 && "border-t border-border-card",
                  )}
                >
                  <History size={15} className="text-fg-subtle" />
                  <p className="flex-1 min-w-0 text-sm">
                    {accessChangeLabel(entry, t)}
                  </p>
                  <span className="text-sm text-fg-subtle">
                    {formatRelativeTime(entry.created_at, language)}
                  </span>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}
    </div>
  </TabsContent>
);

export default UserAccessDetailsTab;
