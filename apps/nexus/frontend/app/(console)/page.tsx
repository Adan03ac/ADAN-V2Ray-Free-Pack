"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Boxes,
  CircleDot,
  Clock3,
  Database,
  Gauge,
  Layers,
  Play,
  Radio,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";

import { ActivityChart, GrowthChart, HealthDonut, Heatmap, LatencyChart, ProtocolBars, RingGauge } from "@/components/charts";
import { KpiCard } from "@/components/shared/kpi-card";
import { EmptyState, ErrorState, InfoNote, MonoStat, Section } from "@/components/shared/page";
import { RunStatusPill } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { formatDateTime, formatLatency, formatNumber, relativeTime } from "@/lib/format";
import { useIsAdmin, useMe } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";
import type { DashboardSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function OverviewPage() {
  const { t, language } = useT();
  const range = useUiStore((state) => state.range);
  const queryClient = useQueryClient();
  const isAdmin = useIsAdmin();
  const me = useMe();

  const summary = useQuery({
    queryKey: ["dashboard", range],
    queryFn: () => api.get<DashboardSummary>(`/dashboard/summary?days=${range}`),
    refetchInterval: 90_000,
  });

  const runIngestion = useMutation({
    mutationFn: () => api.post("/automation/refresh"),
    onSuccess: () => {
      toast("success", t("automation.triggered"), t("sources.refreshHint"));
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["automation"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  if (summary.isLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-3">
          <Skeleton className="h-[268px] rounded-3xl xl:col-span-2" />
          <Skeleton className="h-[268px] rounded-3xl" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <SkeletonCard key={index} />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-64 rounded-3xl" />
          ))}
        </div>
      </div>
    );
  }

  if (summary.isError || !summary.data) {
    return <ErrorState title={t("state.error.title")} detail={(summary.error as Error)?.message} onRetry={() => summary.refetch()} />;
  }

  const data = summary.data;
  const kpis = data.overview.kpis;
  const todayAdded = data.growth[data.growth.length - 1]?.added ?? 0;
  const coverage = kpis.unique_configurations ? kpis.tested_configurations / kpis.unique_configurations : 0;
  const healthySources = data.overview.sources.filter((source) => !source.last_error).length;
  const sourceHealth = data.overview.sources.length ? healthySources / data.overview.sources.length : 0;

  return (
    <div className="space-y-4 animate-fade-up">
      {/* Hero + live rail */}
      <div className="grid gap-4 xl:grid-cols-3">
        <section className="relative overflow-hidden rounded-3xl bg-neon p-5 text-ink-950 shadow-[0_30px_80px_-50px_rgba(157,255,0,0.65)] lg:p-7 xl:col-span-2">
          <div className="pointer-events-none absolute inset-0 opacity-[0.16]" aria-hidden="true">
            <svg viewBox="0 0 600 300" className="absolute -end-16 -top-16 size-[520px]">
              {[0, 1, 2, 3, 4].map((ring) => (
                <circle
                  key={ring}
                  cx="300"
                  cy="150"
                  r={70 + ring * 34}
                  fill="none"
                  stroke="#080A0B"
                  strokeWidth={ring === 0 ? 1.5 : 1}
                />
              ))}
            </svg>
          </div>
          <div className="relative flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="grid size-6 place-items-center rounded-lg bg-ink-950 text-neon">
                  <Layers className="size-3.5" />
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-950/70">
                  {t("overview.hero.eyebrow")}
                </p>
              </div>
              <p className="mt-4 font-mono text-[52px] font-medium leading-none tracking-[-0.04em] lg:text-[68px]">
                {formatNumber(kpis.unique_configurations, language)}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] font-medium text-ink-950/75">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-ink-950/10 px-2.5 py-1">
                  <ArrowUpRight className="size-3.5" />
                  +{formatNumber(todayAdded, language)} {t("overview.hero.added")}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <CircleDot className="size-3.5" />
                  {formatNumber(kpis.total_configurations, language)} links indexed
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Clock3 className="size-3.5" />
                  {kpis.last_successful_update ? relativeTime(kpis.last_successful_update, language) : t("common.never")}
                </span>
              </div>
            </div>
            <div className="flex shrink-0 flex-col items-center gap-3 sm:items-end">
              <RingGauge
                value={kpis.tested_configurations}
                max={Math.max(kpis.unique_configurations, 1)}
                label={`${Math.round(coverage * 100)}%`}
                caption={t("overview.hero.coverage")}
              />
              <Button
                variant="secondary"
                className="border-ink-950/15 bg-ink-950 text-neon hover:bg-ink-900"
                onClick={() => runIngestion.mutate()}
                disabled={!isAdmin || runIngestion.isPending}
                title={isAdmin ? t("overview.hero.action") : t("common.readOnly")}
              >
                <Play className="size-3.5" />
                {runIngestion.isPending ? t("common.loading") : t("overview.hero.action")}
              </Button>
            </div>
          </div>
          <div className="relative mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              { label: t("overview.kpi.sources"), value: `${formatNumber(kpis.active_sources, language)}` },
              { label: t("overview.kpi.reachable"), value: `${formatNumber(kpis.reachable_configurations, language)}` },
              { label: t("overview.kpi.sourceErrors"), value: `${formatNumber(kpis.sources_with_errors, language)}` },
              {
                label: t("overview.kpi.latency"),
                value: kpis.average_measured_latency_ms !== null ? formatLatency(kpis.average_measured_latency_ms) : "—",
              },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl bg-ink-950/[0.07] px-3 py-2.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-ink-950/60">{item.label}</p>
                <p className="mono mt-1 text-sm font-medium text-ink-950">{item.value}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="flex flex-col gap-4">
          <Section
            title={t("overview.rail.sources")}
            action={
              <Link href="/sources" className="text-[11px] text-chalk-500 transition-colors hover:text-neon">
                {t("overview.rail.viewAll")}
              </Link>
            }
            padded
            className="flex-1"
          >
            <div className="-mt-1 space-y-1.5">
              {data.overview.sources.slice(0, 4).map((source) => (
                <div
                  key={source.id}
                  className="flex items-center gap-2.5 rounded-2xl border border-white/[0.04] bg-ink-950/40 p-2.5"
                >
                  <span
                    className={cn(
                      "grid size-8 shrink-0 place-items-center rounded-full font-mono text-[11px] uppercase",
                      source.last_error
                        ? "bg-signal-danger/15 text-signal-danger"
                        : source.enabled
                          ? "bg-neon/15 text-neon"
                          : "bg-white/[0.06] text-chalk-500",
                    )}
                  >
                    {source.name.slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] text-chalk-200">{source.name}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-chalk-500">
                      <span
                        className={cn(
                          "size-1.5 rounded-full",
                          source.last_error ? "bg-signal-danger" : source.enabled ? "bg-neon" : "bg-chalk-500",
                        )}
                      />
                      {source.last_error ? "error" : source.enabled ? "active" : "disabled"}
                      <span className="text-chalk-500/60">·</span>
                      {source.last_success_at ? relativeTime(source.last_success_at, language) : t("common.never")}
                    </p>
                  </div>
                  <span className="mono shrink-0 text-[11px] text-chalk-400">{formatNumber(source.config_count, language)}</span>
                </div>
              ))}
              {!data.overview.sources.length ? (
                <p className="py-6 text-center text-xs text-chalk-500">{t("sources.empty")}</p>
              ) : null}
            </div>
          </Section>

          <Section title={t("overview.rail.activity")} className="flex-1" padded>
            <ul className="-mt-1 space-y-2.5">
              {data.latest_events.slice(0, 4).map((event) => (
                <li key={event.id} className="flex items-start gap-2.5">
                  <span
                    className={cn(
                      "mt-1.5 size-1.5 shrink-0 rounded-full",
                      event.status === "failed"
                        ? "bg-signal-danger"
                        : event.status === "partial"
                          ? "bg-signal-warning"
                          : "bg-neon",
                    )}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] leading-snug text-chalk-300">
                      Run <span className="mono text-chalk-100">#{event.id}</span> accepted{" "}
                      <span className="mono text-neon">{formatNumber(event.accepted, language)}</span> links
                      {event.new ? <span className="text-chalk-500"> · {formatNumber(event.new, language)} new</span> : null}
                    </p>
                    <p className="mt-0.5 text-[10px] text-chalk-500">
                      {event.trigger} · {relativeTime(event.started_at, language)}
                    </p>
                  </div>
                </li>
              ))}
              {!data.latest_events.length ? (
                <li className="py-4 text-center text-xs text-chalk-500">{t("automation.empty")}</li>
              ) : null}
            </ul>
          </Section>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={t("overview.kpi.total")} value={formatNumber(kpis.total_configurations, language)} hint={t("overview.kpi.totalHint")} icon={Database} />
        <KpiCard
          label={t("overview.kpi.tested")}
          value={formatNumber(kpis.tested_configurations, language)}
          hint={t("overview.kpi.testedHint")}
          icon={Gauge}
          tone="violet"
        />
        <KpiCard
          label={t("overview.kpi.reachable")}
          value={formatNumber(kpis.reachable_configurations, language)}
          hint={t("overview.kpi.reachableHint")}
          icon={Radio}
          tone="neon"
        />
        <KpiCard
          label={t("overview.kpi.verified")}
          value={formatNumber(kpis.verified_working_configurations, language)}
          hint={`${t("overview.verificationOff")} · ${t("overview.kpi.verifiedHint")}`}
          icon={ShieldAlert}
          tone="warning"
        />
      </div>

      {!kpis.unique_configurations ? (
        <InfoNote tone="info">{t("overview.empty")}</InfoNote>
      ) : null}

      {/* Charts row */}
      <div className="grid gap-4 lg:grid-cols-12">
        <Section
          className="lg:col-span-5"
          title={t("overview.chart.growth")}
          hint={t("overview.chart.growthHint")}
          action={<Badge tone="muted">{t(`range.${range}`)}</Badge>}
          padded
        >
          <GrowthChart data={data.growth} language={language} height={190} />
        </Section>

        <Section className="lg:col-span-3" title={t("overview.chart.health")} hint={t("overview.chart.healthHint")} padded>
          <HealthDonut distribution={data.overview.health_distribution} language={language} height={168} />
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-chalk-500">
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-neon" /> reachable {formatNumber(data.overview.health_distribution.reachable ?? 0, language)}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-signal-danger" /> failed {formatNumber(data.overview.health_distribution.failed ?? 0, language)}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-1.5 rounded-full bg-chalk-500/50" /> untested{" "}
              {formatNumber(data.overview.health_distribution.untested ?? 0, language)}
            </span>
          </div>
        </Section>

        <Section className="lg:col-span-4" title={t("overview.chart.heatmap")} hint={t("overview.chart.heatmapHint")} padded>
          <Heatmap cells={data.heatmap.cells} language={language} />
          <div className="mt-3 flex items-center justify-between rounded-xl bg-white/[0.02] px-3 py-2 text-[10px] text-chalk-500">
            <span>{formatNumber(data.heatmap.max_added, language)} peak daily additions</span>
            <span className="mono">{data.heatmap.weeks}w</span>
          </div>
        </Section>

        <Section className="lg:col-span-4" title={t("overview.chart.protocols")} hint={t("overview.chart.protocolsHint")} padded>
          <ProtocolBars items={data.overview.protocol_distribution} language={language} />
        </Section>

        <Section className="lg:col-span-4" title={t("overview.chart.latency")} hint={t("overview.chart.latencyHint")} padded>
          <LatencyChart data={data.latency_trend} language={language} height={172} />
          <p className="mt-1 text-[10px] text-chalk-500">
            Agent: <span className="mono">{data.health.agent.label}</span> · {data.health.agent.region}
          </p>
        </Section>

        <Section className="lg:col-span-4" title={t("overview.chart.activity")} hint={t("overview.chart.activityHint")} padded>
          <ActivityChart data={data.pipeline_activity} language={language} height={172} />
          <p className="mt-1 text-[10px] text-chalk-500">
            {formatNumber(data.pipeline_activity.reduce((sum, item) => sum + item.runs, 0), language)} runs ·{" "}
            {formatNumber(data.pipeline_activity.reduce((sum, item) => sum + item.accepted, 0), language)} accepted
          </p>
        </Section>
      </div>

      {/* Runs + operations */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Section
          className="xl:col-span-2"
          title={t("automation.runs")}
          hint={t("overview.rail.activity")}
          action={
            <Button asChild variant="ghost" size="sm">
              <Link href="/automation">{t("overview.quick.automation")}</Link>
            </Button>
          }
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-[10px] uppercase tracking-[0.12em] text-chalk-500">
                  <th className="px-5 py-2 text-start font-medium">Run</th>
                  <th className="px-3 py-2 text-start font-medium">{t("common.status")}</th>
                  <th className="px-3 py-2 text-start font-medium">{t("automation.col.started")}</th>
                  <th className="px-3 py-2 text-end font-medium">{t("automation.col.sources")}</th>
                  <th className="px-3 py-2 text-end font-medium">{t("automation.col.accepted")}</th>
                  <th className="px-5 py-2 text-end font-medium">{t("automation.col.published")}</th>
                </tr>
              </thead>
              <tbody>
                {data.latest_events.map((event) => (
                  <tr key={event.id} className="table-row-hover border-b border-white/[0.03]">
                    <td className="px-5 py-2.5">
                      <span className="mono text-xs text-chalk-200">#{event.id}</span>
                      <span className="ms-2 text-[10px] text-chalk-500">{event.trigger}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <RunStatusPill status={event.status} />
                    </td>
                    <td className="px-3 py-2.5 text-[11px] text-chalk-400">{formatDateTime(event.started_at, language)}</td>
                    <td className="mono px-3 py-2.5 text-end text-[11px] text-chalk-400">
                      {event.sources_ok}/{event.sources_ok + event.sources_failed}
                    </td>
                    <td className="mono px-3 py-2.5 text-end text-[11px] text-neon">{formatNumber(event.accepted, language)}</td>
                    <td className="px-5 py-2.5 text-end text-[11px]">
                      {event.published ? (
                        <span className="text-signal-success">published</span>
                      ) : (
                        <span className="text-chalk-500">{event.publish_skipped_reason ? "skipped" : "—"}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.latest_events.length ? <EmptyState title={t("automation.empty")} /> : null}
          </div>
        </Section>

        <div className="flex flex-col gap-4">
          <Section title={t("overview.scheduler")} hint={t("overview.schedulerApprox")} padded>
            <div className="space-y-2.5 text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-chalk-500">{t("overview.scheduler")}</span>
                <MonoStat>{data.scheduler.next_run_at ? formatDateTime(data.scheduler.next_run_at, language) : "—"}</MonoStat>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-chalk-500">Interval</span>
                <MonoStat>{data.scheduler.interval_minutes} min</MonoStat>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-chalk-500">Scheduler</span>
                <Badge tone={data.scheduler.running ? "success" : "muted"}>
                  {data.scheduler.running ? "running" : "stopped"}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-chalk-500">{t("overview.publication")}</span>
                <Badge tone="violet">{data.publication.provider}</Badge>
              </div>
            </div>
            <div className="mt-3 rounded-xl border border-white/[0.05] bg-ink-950/50 p-2.5">
              <p className="text-[10px] uppercase tracking-wider text-chalk-500">{t("overview.upstream")}</p>
              {data.upstream.available ? (
                <div className="mt-1.5 flex items-center justify-between text-[11px]">
                  <span className="text-chalk-400">{formatNumber(data.upstream.total ?? 0, language)} {t("overview.upstreamTotal")}</span>
                  <span className="text-chalk-500">{data.upstream.updated_at_utc ? relativeTime(data.upstream.updated_at_utc, language) : "—"}</span>
                </div>
              ) : (
                <p className="mt-1.5 text-[10px] text-chalk-500">{t("overview.upstreamUnavailable")}</p>
              )}
            </div>
          </Section>

          <Section title={t("overview.quick")} padded>
            <div className="grid gap-2">
              <Button variant="secondary" size="sm" className="justify-start" asChild>
                <Link href="/sources">
                  <Radio /> {t("nav.sources")}
                </Link>
              </Button>
              <Button variant="secondary" size="sm" className="justify-start" asChild>
                <Link href="/configurations">
                  <Boxes /> {t("overview.quick.explore")}
                </Link>
              </Button>
              <Button variant="secondary" size="sm" className="justify-start" asChild>
                <Link href="/subscriptions">
                  <Layers /> {t("overview.quick.studio")}
                </Link>
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="justify-start"
                onClick={() => runIngestion.mutate()}
                disabled={!isAdmin || runIngestion.isPending}
              >
                <RefreshCw className={cn(runIngestion.isPending && "animate-spin")} /> {t("overview.quick.refresh")}
              </Button>
            </div>
            {data.recent_source_errors.length ? (
              <div className="mt-3 space-y-1.5">
                {data.recent_source_errors.slice(0, 2).map((source) => (
                  <div key={source.id} className="rounded-xl border border-signal-danger/15 bg-signal-danger/[0.05] p-2.5">
                    <p className="flex items-center gap-1.5 text-[10px] text-signal-danger">
                      <TriangleAlert className="size-3" /> {source.name}
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-[10px] text-chalk-500">{source.last_error}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 flex items-center gap-1.5 text-[10px] text-chalk-500">
                <ShieldCheck className="size-3.5 text-signal-success" /> {t("automation.noErrors")}
              </p>
            )}
            <p className="mt-3 text-[10px] leading-relaxed text-chalk-500">
              Signed in as <span className="text-chalk-300">{me.data?.user.email}</span>. All statistics are database
              aggregates; missing telemetry is shown as empty, never estimated.
            </p>
          </Section>
        </div>
      </div>

      <div className="rounded-2xl border border-white/[0.05] bg-white/[0.015] px-4 py-3 text-[10px] leading-relaxed text-chalk-500">
        <span className="text-chalk-400">{t("overview.kpi.verified")}: </span>
        {formatNumber(kpis.verified_working_configurations, language)} — {kpis.verification_note}
      </div>
    </div>
  );
}
