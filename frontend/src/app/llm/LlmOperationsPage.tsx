import React from "react";
import { Activity } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Card, FormAlert, LoadingState, PageContainer } from "../sdk";
import { useLlmProviderOperationsQuery } from "./llmQueries";

const LlmOperationsPage: React.FC = () => {
    const { t } = useTranslation("llm");
    const { data, isLoading, isError } = useLlmProviderOperationsQuery();

    if (isLoading) return <LoadingState message={t("operationsLoading")} />;
    if (isError || !data) return <FormAlert status="error">{t("operationsUnavailable")}</FormAlert>;

    const successRate = data.probes ? Math.round((data.reachable_probes / data.probes) * 100) : null;
    const checkedAt = data.last_checked_at ? new Date(data.last_checked_at).toLocaleString() : t("notAvailable");

    return (
        <PageContainer title={t("operationsTitle")} icon={Activity} description={t("operationsDescription")}>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Card className="p-5"><p className="text-sm text-fg-muted">{t("provider")}</p><p className="mt-2 text-xl font-semibold">{data.provider}</p><p className="text-sm text-fg-muted">{data.model}</p></Card>
                <Card className="p-5"><p className="text-sm text-fg-muted">{t("probeSuccessRate")}</p><p className="mt-2 text-xl font-semibold">{successRate === null ? t("notAvailable") : `${successRate}%`}</p><p className="text-sm text-fg-muted">{t("probeCount", { count: data.probes })}</p></Card>
                <Card className="p-5"><p className="text-sm text-fg-muted">{t("averageLatency")}</p><p className="mt-2 text-xl font-semibold">{data.average_latency_ms === null ? t("notAvailable") : `${data.average_latency_ms} ms`}</p><p className="text-sm text-fg-muted">{t("failedProbes", { count: data.failed_probes })}</p></Card>
                <Card className="p-5"><p className="text-sm text-fg-muted">{t("lastChecked")}</p><p className="mt-2 text-base font-semibold">{checkedAt}</p><p className="text-sm text-fg-muted">{data.last_error_code ?? t("noRecentError")}</p></Card>
            </div>
        </PageContainer>
    );
};

export default LlmOperationsPage;
