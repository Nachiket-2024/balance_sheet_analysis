import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Input, type InputProps } from "../inputs/Input";
import { Button } from "../buttons/Button";

// Forwards every Input prop except `type`, which this component owns so it
// can toggle between "password" and "text" internally.
type PasswordInputProps = Omit<InputProps, "type">;

const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(({ className, ...props }, ref) => {
    const { t } = useTranslation("ui_text");
    const [visible, setVisible] = useState(false);

    return (
        <div className="relative">
            <Input ref={ref} type={visible ? "text" : "password"} className={`pe-9 ${className ?? ""}`} {...props} />
            <Button
                type="button"
                aria-label={visible ? t("hidePassword") : t("showPassword")}
                variant="ghost"
                size="icon-sm"
                // This is a real keyboard action, not decorative input chrome:
                // keep it in the tab order so keyboard and switch users can
                // reveal or hide the password too.
                className="absolute inset-y-0 end-0.5 my-auto text-fg-muted hover:bg-[var(--gray-200)] hover:text-fg-default focus-visible:bg-[var(--gray-200)] focus-visible:text-fg-default focus-visible:ring-2 focus-visible:ring-brand-solid focus-visible:ring-offset-1 dark:hover:bg-[var(--gray-700)] dark:focus-visible:bg-[var(--gray-700)] dark:focus-visible:ring-offset-bg-surface"
                onClick={() => setVisible((v) => !v)}
            >
                {visible ? <EyeOff size={16} /> : <Eye size={16} />}
            </Button>
        </div>
    );
});
PasswordInput.displayName = "PasswordInput";

export default PasswordInput;
