import React from "react";
import { LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "../../ui/buttons/Button";

interface LogoutButtonComponentProps {
    loading: boolean;
    error: string | null;
    successMessage: string | null;
    onLogout: () => void;
}

const LogoutButtonComponent: React.FC<LogoutButtonComponentProps> = ({
    loading,
    error,
    successMessage,
    onLogout,
}) => {
    const { t } = useTranslation("auth");

    return (
        <div className="flex flex-col items-center">
            {/* design/dashboard.html's `.btn.btn-danger`: hug-content width,
                600 label, a 14px LogOut icon with a 6px gap - not a fixed
                160x40 box (the previous size="lg" w="40" h="10"), which
                rendered noticeably larger/blockier than the mockup's topbar
                Logout button. h-8 + text-sm match ControlCluster's icon-sm
                buttons (FontSizeControl/LanguageToggle/ThemeToggle) and the
                rest of Navbar's text right beside it, which the earlier
                h-auto + 9px padding + 16px text overshot. Only renders here
                (Navbar's chrome), so this resize has no other caller to
                consider. */}
            <Button
                onClick={onLogout}
                loading={loading}
                variant="destructive"
                className="bg-[var(--red-600)] text-sm font-semibold px-4 h-8 rounded-[var(--radius-control)] gap-1.5"
            >
                <LogOut size={14} aria-hidden="true" />
                {t("logout.logoutButton")}
            </Button>

            {error && (
                <p className="text-[var(--red-500)] text-base">
                    {error}
                </p>
            )}

            {successMessage && (
                <p className="text-[var(--green-500)] text-base">
                    {successMessage}
                </p>
            )}
        </div>
    );
};

export default LogoutButtonComponent;
