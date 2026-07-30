import React from "react";

import { useAuthStore } from "../../store/authStore";
import settings from "../../core/settings";
import OAuth2LoginButtonComponent from "./OAuth2LoginButtonComponent";

interface OAuth2ButtonProps {
    onSuccess?: () => void;
    onAttempt?: () => void;
}

// This button never makes an API call of its own, it's a full-page
// redirect to the backend's OAuth2 endpoint, which handles the Google
// callback server-side and redirects back with the session cookie already
// set. `error`/`isAuthenticated`/`user` below are static empty values
// because nothing in the frontend populates them (there is no frontend
// OAuth2 callback route); only `globalAuth`, the real shared session
// status, carries live data.
const OAuth2LoginButton: React.FC<OAuth2ButtonProps> = ({ onAttempt }) => {
    const globalAuth = useAuthStore((s) => !!s.isAuthenticated);

    const handleLogin = () => {
        onAttempt?.();
        window.location.href = `${settings.apiBaseUrl}/auth/oauth2/login/google`;
    };

    return (
        <OAuth2LoginButtonComponent
            error={null}
            isAuthenticated={false}
            user={null}
            globalAuth={globalAuth}
            onLogin={handleLogin}
        />
    );
};

export default OAuth2LoginButton;
