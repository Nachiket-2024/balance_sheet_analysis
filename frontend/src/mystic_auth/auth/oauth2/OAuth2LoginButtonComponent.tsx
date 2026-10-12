import React from "react";
import { useTranslation } from "react-i18next";

import FormAlert from "../../ui/feedback/FormAlert";
import { Button } from "../../ui/buttons/Button";

interface OAuth2LoginButtonComponentProps {
    error: string | null;
    isAuthenticated: boolean;
    user: { id: string; email: string; role: string } | null;
    globalAuth: boolean;
    onLogin: () => void;
    label?: string;
}

const OAuth2LoginButtonComponent: React.FC<OAuth2LoginButtonComponentProps> = ({
    error,
    isAuthenticated,
    user,
    globalAuth,
    onLogin,
    label,
}) => {
    const { t } = useTranslation("auth");

    return (
        <div className="w-full mt-4">
            <Button
                variant="outline"
                // Google's branding guidelines offer a light and dark button variant; this
                // switches with the app theme instead of always using the light one.
                className="w-full bg-white text-[#1F1F1F] border-[#747775] hover:bg-[#f3f4f6] hover:border-[#5f6368] hover:text-[#1F1F1F] dark:bg-[#131314] dark:text-[#E3E3E3] dark:border-[#8E918F] dark:hover:bg-[#242528] dark:hover:border-[#c4c7c5] dark:hover:text-[#E3E3E3] transition-colors duration-100"
                size="lg"
                onClick={onLogin}
            >
                <div className="flex items-center justify-center gap-2">
                    <svg width="20" height="20" viewBox="0 0 533.5 544.3" aria-hidden="true">
                        <path fill="#4285F4" d="M533.5 278.4c0-17.5-1.5-34.4-4.3-50.7H272v95.9h146.9c-6.3 33.9-25.5 62.7-54.5 82v68h87.8c51.4-47.4 80.3-116.9 80.3-195.2z"/>
                        <path fill="#34A853" d="M272 544.3c73.7 0 135.5-24.3 180.7-66.2l-87.8-68c-24.4 16.4-55.7 26-92.9 26-71.5 0-132.2-48.1-153.9-112.7h-90.6v70.8c45.3 90 138.5 150.1 244.5 150.1z"/>
                        <path fill="#FBBC05" d="M118.3 323.2c-10.7-32-10.7-66.6 0-98.6v-70.8h-90.6c-40.2 78.7-40.2 171.1 0 249.8l90.6-70.4z"/>
                        <path fill="#EA4335" d="M272 107.7c39.8-.6 77.7 14 106.6 40.8l79.9-79.9C405.9 21 345.7-4.3 272 0 166 0 72.8 60.1 27.5 150.1l90.6 70.8C139.8 155.8 200.5 107.7 272 107.7z"/>
                    </svg>
                    <span>{label ?? t("oauth2.signInWithGoogle")}</span>
                </div>
            </Button>

            {error && (
                <div className="mt-2">
                    <FormAlert status="error">{error}</FormAlert>
                </div>
            )}

            {(isAuthenticated || globalAuth) && user && (
                <div className="mt-2">
                    <FormAlert status="success">
                        {t("oauth2.welcomeUser", { email: user.email, role: user.role })}
                    </FormAlert>
                </div>
            )}
        </div>
    );
};

export default OAuth2LoginButtonComponent;
