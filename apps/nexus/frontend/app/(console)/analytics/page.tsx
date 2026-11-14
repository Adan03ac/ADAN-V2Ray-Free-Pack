"use client";

import { useQuery } from "@tanstack/react-query";

import { ActivityChart, GrowthChart, HealthDonut, Heatmap, LatencyChart, ProtocolBars } from "@/components/charts";
import { ErrorState, PageHeader, Section } from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDuration, formatNumber, formatPercent } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";

interface ReliabilityRow {
  source_id: number;
  name: string;
  fetches: number;
  success_rate: number | null;
  errors: number;
  avg_duration_ms: number | null;
  consecutive_failures: number;
}

interface AnalyticsOverview {
  overview: {
    kpis: { unique_configurations: number; total_configurations: number; average_measured_latency_ms: number | null };
    protocol_distribution: Array<{ protocol: string; count: number; share: number }>;
    health_distribution: Record<string, number>;
  };
  source_contribution: Array<{ source_id: number; name: string; configurations: number; occurrences: number; share: number }>;
  source_reliability: ReliabilityRow[];
}

interface Series {
  days: number;
  growth: Array<{ date: string; added: number; cumulative: number }>;
  latency_trend: Array<{ date: string; avg_latency_ms: number | null; samples: number }>;
  pipeline_activity: Array<{ date: string; runs: number; accepted: number; new: number }>;
  heatmap: { weeks: number; cells: Array<{ date: string; added: number; tests: number; runs: number; intensity: number }>; max_added: number };
}

export default function AnalyticsPage() {
  const { t, language } = useT();
  const range = useUiStore((state) => state.range);

  const overview = useQuery({ queryKey: ["analytics-overview"], queryFn: () => api.get<AnalyticsOverview>("/analytics/overview") });
  const series = useQuery({ queryKey: ["analytics-series", range], queryFn: () => api.get<Series>(`/analytics/series?days=${range}`) });

  if (overview.isLoading || series.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-64 rounded-3xl" />
          ))}
        </div>
      </div>
    );
  }

  if (overview.isError || series.isError || !overview.data || !series.data) {
    return (
      <ErrorState
        title={t("state.error.title")}
        detail={((overview.error ?? series.error) as Error)?.message}
        onRetry={() => {
          overview.refetch();
          series.refetch();
        }}
      />
    );
  }

  const kpis = overview.data.overview.kpis;
  const reliability = overview.data.source_reliability;

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("analytics.title")}
        subtitle={t("analytics.subtitle")}
        actions={<Badge tone="muted">{t(`range.${range}`)}</Badge>}
      />

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: t("overview.kpi.unique"), value: formatNumber(kpis.unique_configurations, language) },
          { label: t("overview.kpi.total"), value: formatNumber(kpis.total_configurations, language) },
          {
            label: t("overview.kpi.latency"),
            value: kpis.average_measured_latency_ms !== null ? `${kpis.average_measured_latency_ms.toFixed(1)} ms` : "—",
          },
        ].map((item) => (
          <div key={item.label} className="card-surface p-4">
            <p className="text-[10px] uppercase tracking-[0.14em] text-chalk-500">{item.label}</p>
            <p className="mono mt-2 text-2xl text-chalk-100">{item.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        <Section className="lg:col-span-8" title={t("analytics.growth")} hint={t("overview.chart.growthHint")} padded>
          <GrowthChart data={series.data.growth} language={language} height={230} />
        </Section>
        <Section className="lg:col-span-4" title={t("analytics.health")} hint={t("overview.chart.healthHint")} padded>
          <HealthDonut distribution={overview.data.overview.health_distribution} language={language} height={190} />
        </Section>

        <Section className="lg:col-span-4" title={t("analytics.contribution")} hint={t("overview.chart.protocolsHint")} padded>
          <ul className="space-y-3">
            {overview.data.source_contribution.map((source) => (
              <li key={source.source_id}>
                <div className="flex items-baseline justify-between gap-2 text-[11px]">
                  <span className="truncate text-chalk-300">{source.name}</span>
                  <span className="mono shrink-0 text-chalk-500">{formatPercent(source.share)}</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
                  <div className="h-full rounded-full bg-violet" style={{ width: `${Math.max(2, source.share * 100)}%` }} />
                </div>
                <p className="mono mt-1 text-[10px] text-chalk-500">
                  {formatNumber(source.configurations, language)} configurations · {formatNumber(source.occurrences, language)} occurrences
                </p>
              </li>
            ))}
            {!overview.data.source_contribution.length ? <li className="text-xs text-chalk-500">{t("analytics.empty")}</li> : null}
          </ul>
        </Section>

        <Section className="lg:col-span-4" title={t("overview.chart.protocols")} hint={t("overview.chart.protocolsHint")} padded>
          <ProtocolBars items={overview.data.overview.protocol_distribution} language={language} />
        </Section>

        <Section className="lg:col-span-4" title={t("analytics.latency")} hint={t("overview.chart.latencyHint")} padded>
          <LatencyChart data={series.data.latency_trend} language={language} height={190} />
        </Section>

        <Section className="lg:col-span-6" title={t("analytics.activity")} hint={t("overview.chart.activityHint")} padded>
          <ActivityChart data={series.data.pipeline_activity} language={language} height={180} />
        </Section>

        <Section className="lg:col-span-6" title={t("overview.chart.heatmap")} hint={t("overview.chart.heatmapHint")} padded>
          <Heatmap cells={series.data.heatmap.cells} language={language} />
        </Section>
      </div>

      <Section title={t("analytics.reliability")} hint={t("analytics.fetchSuccess")}>
        <TableWrap>
          <Table className="min-w-[760px]">
            <thead>
              <tr>
                <Th>{t("sources.col.name")}</Th>
                <Th className="text-end">{t("analytics.fetches")}</Th>
                <Th className="text-end">{t("analytics.fetchSuccess")}</Th>
                <Th className="text-end">{t("sources.col.errors")}</Th>
                <Th className="text-end">{t("sources.detail.duration")}</Th>
                <Th className="text-end">{t("common.status")}</Th>
              </tr>
            </thead>
            <tbody>
              {reliability.map((row) => (
                <Tr key={row.source_id}>
                  <Td className="text-[12px] text-chalk-200">{row.name}</Td>
                  <Td className="mono text-end text-[11px]">{formatNumber(row.fetches, language)}</Td>
                  <Td className="mono text-end text-[11px] text-neon">{row.success_rate !== null ? formatPercent(row.success_rate) : "—"}</Td>
                  <Td className="mono text-end text-[11px] text-chalk-400">{formatNumber(row.errors, language)}</Td>
                  <Td className="mono text-end text-[11px] text-chalk-400">{formatDuration(row.avg_duration_ms)}</Td>
                  <Td className="text-end">
                    <Badge tone={row.consecutive_failures ? "danger" : row.fetches ? "success" : "muted"}>
                      {row.consecutive_failures ? "error" : row.fetches ? "ok" : "never"}
                    </Badge>
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </TableWrap>
      </Section>
    </div>
  );
}
