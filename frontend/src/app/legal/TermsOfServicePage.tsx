import React from "react";
import { useTranslation } from "react-i18next";

import { APP_NAME, SUPPORT_EMAIL } from "../sdk";
import LegalDocumentLayout, { type LegalSection } from "./LegalDocumentLayout";

// See PrivacyPolicyPage.tsx for where this content lives and how to update it.
const TermsOfServicePage: React.FC = () => {
    const { t } = useTranslation("legal");

    const contactPlaceholder = SUPPORT_EMAIL || t("operatorContactPlaceholder");
    const entityPlaceholder = t("operatorEntityPlaceholder");
    const interpolation = { appName: APP_NAME, contactPlaceholder, entityPlaceholder };

    return (
        <LegalDocumentLayout
            title={t("terms.title", interpolation)}
            lastUpdatedLabel={t("lastUpdatedLabel")}
            lastUpdatedDate={t("lastUpdatedDate")}
            backLabel={t("back")}
            reviewNote={t("operatorReviewNote")}
            intro={t("terms.intro", { ...interpolation, returnObjects: true }) as string[]}
            sections={t("terms.sections", { ...interpolation, returnObjects: true }) as LegalSection[]}
        />
    );
};

export default TermsOfServicePage;
