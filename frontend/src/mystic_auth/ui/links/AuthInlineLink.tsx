import React from "react";
import { Link as RouterLink } from "react-router";

import { cn } from "../styles/classNames";

// Centralizes the underline/darken hover cue for auth-page links (LoginForm,
// LoginPage, PasswordResetRequestPage, PasswordResetConfirmPage, SignupForm),
// which used to be plain react-router Links with no hover state. Props are
// RouterLink's own plus className, so callers can still hand in extra
// Tailwind classes (e.g. AccountSettingsPage's text-base).
const AuthInlineLink: React.FC<React.ComponentProps<typeof RouterLink>> = ({ className, ...props }) => (
    <RouterLink
        className={cn(
            "text-brand-fg font-semibold no-underline hover:text-[var(--brand-600)] hover:underline",
            "transition-[background-color,border-color,color] duration-[var(--duration-hover)] ease-[var(--easing-hover)]",
            className
        )}
        {...props}
    />
);

export default AuthInlineLink;
