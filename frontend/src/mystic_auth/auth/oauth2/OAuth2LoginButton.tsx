import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { useAuthStore } from "../../store/authStore";
import settings from "../../core/settings";
import { translateErrorCode } from "../../api/apiError";
import OAuth2LoginButtonComponent from "./OAuth2LoginButtonComponent";

interface OAuth2ButtonProps {
    onSuccess?: () => void;
    onAttempt?: () => void;
    label?: string;
}

// A full-page redirect to the backend's OAuth2 endpoint, not an API call. It handles
// the Google callback server-side and redirects back to /login with `?error=<code>`
// on failure. `error` is read from that param once on mount, translated like API
// errors, then stripped from the URL so a refresh doesn't re-show it. There is no
// frontend OAuth2 callback route.
const OAuth2LoginButton: React.FC<OAuth2ButtonProps> = ({ onAttempt, label }) => {
    const globalAuth = useAuthStore((s) => !!s.isAuthenticated);
    const [searchParams, setSearchParams] = useSearchParams();
    // Lazy initializer reads `error` once during the first render, avoiding an
    // extra render via setState in an effect.
    const [error] = useState<string | null>(() => {
        const errorCode = searchParams.get("error");
        return errorCode ? translateErrorCode(errorCode) : null;
    });

    useEffect(() => {
        if (!searchParams.get("error")) {
            return;
        }

        setSearchParams(
            (prev) => {
                const next = new URLSearchParams(prev);
                next.delete("error");
                return next;
            },
            { replace: true }
        );
        // Only the error param from the initial redirect back from Google matters;
        // deliberately not re-running on every searchParams change.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleLogin = () => {
        onAttempt?.();
        window.location.href = `${settings.apiBaseUrl}/auth/oauth2/login/google`;
    };

    return (
        <OAuth2LoginButtonComponent
            error={error}
            isAuthenticated={false}
            user={null}
            globalAuth={globalAuth}
            onLogin={handleLogin}
            label={label}
        />
    );
};

export default OAuth2LoginButton;
