import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { useLogoutAllMutation } from "./useLogoutAllMutation";
import LogoutAllButtonComponent from "./LogoutAllButtonComponent";

// This ends every session on every device immediately, including the
// caller's own; worth one extra click via a confirmation dialog to avoid
// an accidental self-logout-everywhere from a stray click.
import ConfirmDialog from "../../ui/ConfirmDialog";

const LogoutAllButton: React.FC = () => {
    const logoutAllMutation = useLogoutAllMutation();
    const navigate = useNavigate();
    const [confirmOpen, setConfirmOpen] = useState(false);

    const handleLogoutAll = () => {
        logoutAllMutation.mutate();
        setConfirmOpen(false);
    };

    useEffect(() => {
        if (logoutAllMutation.isSuccess) {
            navigate("/login");
        }
    }, [logoutAllMutation.isSuccess, navigate]);

    return (
        <>
            <LogoutAllButtonComponent
                loading={logoutAllMutation.isPending}
                error={logoutAllMutation.error?.message ?? null}
                successMessage={logoutAllMutation.data?.message ?? null}
                onLogoutAll={() => setConfirmOpen(true)}
            />
            <ConfirmDialog
                isOpen={confirmOpen}
                title="Logout all devices"
                description="This will end every active session for your account on every device, including this one. Continue?"
                confirmLabel="Logout all"
                isLoading={logoutAllMutation.isPending}
                onConfirm={handleLogoutAll}
                onCancel={() => setConfirmOpen(false)}
            />
        </>
    );
};

export default LogoutAllButton;
