import React from "react";
import { useTranslation } from "react-i18next";

import { APP_NAME, SUPPORT_EMAIL } from "../sdk";
import LegalDocumentLayout, { type LegalSection } from "./LegalDocumentLayout";

// Content lives in mystic_auth/translations/languages/*/legal.json as the
// repository's documented ownership exception: the values are downstream
// deployment content, while the registration and rendering code stays shared.
// Keep it in sync with the codebase's actual data flows (see
// docs/mystic_auth/security/decisions-infra.md for the audit this was written
// against) rather than generic boilerplate.
// Update that file, in every language, whenever a data-collecting field,
// cookie, or third party changes.
const PrivacyPolicyPage: React.FC = () => {
    const { t } = useTranslation("legal");

    const contactPlaceholder = SUPPORT_EMAIL || t("operatorContactPlaceholder");
    const interpolation = { appName: APP_NAME, contactPlaceholder };

    return (
        <LegalDocumentLayout
            title={t("privacy.title", interpolation)}
            lastUpdatedLabel={t("lastUpdatedLabel")}
            lastUpdatedDate={t("lastUpdatedDate")}
            backLabel={t("back")}
            reviewNote={t("operatorReviewNote")}
            intro={t("privacy.intro", { ...interpolation, returnObjects: true }) as string[]}
            sections={t("privacy.sections", { ...interpolation, returnObjects: true }) as LegalSection[]}
        />
    );
};

export default PrivacyPolicyPage;
