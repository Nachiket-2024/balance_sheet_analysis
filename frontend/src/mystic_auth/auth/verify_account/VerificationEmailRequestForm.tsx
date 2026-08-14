import React, { useState } from "react";
import { Button, Input, Stack } from "@chakra-ui/react";
import { Field as ChakraField } from "@chakra-ui/react";
import { useTranslation } from "react-i18next";

import { useVerificationEmailRequestMutation } from "./useVerificationEmailRequestMutation";
import { useCooldown } from "../../ui/hooks/useCooldown";
import FormAlert from "../../ui/FormAlert";
import { BRAND_OUTLINE_HOVER_PROPS } from "../../ui/styles/buttonStyles";
import { useLanguageStore } from "../../store/languageStore";
import { formatNumber } from "../../translations/numerals";

interface VerificationEmailRequestFormProps {
    initialEmail?: string;
}

const VerificationEmailRequestForm: React.FC<VerificationEmailRequestFormProps> = ({ initialEmail = "" }) => {
    const { t } = useTranslation("auth");
    const language = useLanguageStore((s) => s.pageLanguage);
    const [email, setEmail] = useState(initialEmail);
    const { cooldown, startCooldown } = useCooldown();
    const requestMutation = useVerificationEmailRequestMutation();

    const handleSubmit = (e: React.SubmitEvent<HTMLDivElement>) => {
        e.preventDefault();

        if (cooldown > 0) {
            return;
        }

        requestMutation.mutate({ email });
        startCooldown();
    };

    return (
        <Stack as="form" onSubmit={handleSubmit} w="full" gap={3}>
            <ChakraField.Root required>
                <ChakraField.Label>{t("verifyEmailRequest.emailLabel")}</ChakraField.Label>
                <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={t("verifyEmailRequest.emailPlaceholder")}
                    size="lg"
                    disabled={requestMutation.isPending}
                />
            </ChakraField.Root>

            <Button
                type="submit"
                variant="outline"
                borderColor="brand.500"
                color="brand.500"
                size="lg"
                w="full"
                loading={requestMutation.isPending}
                disabled={cooldown > 0 || requestMutation.isPending}
                loadingText={t("verifyEmailRequest.sending")}
                {...BRAND_OUTLINE_HOVER_PROPS}
            >
                {cooldown > 0 ? t("verifyEmailRequest.tryAgainIn", { seconds: formatNumber(cooldown, language) }) : t("verifyEmailRequest.submitButton")}
            </Button>

            {requestMutation.isError && (
                <FormAlert status="error">{requestMutation.error.message}</FormAlert>
            )}

            {requestMutation.isSuccess && (
                <FormAlert status="success">{requestMutation.data.message}</FormAlert>
            )}
        </Stack>
    );
};

export default VerificationEmailRequestForm;
