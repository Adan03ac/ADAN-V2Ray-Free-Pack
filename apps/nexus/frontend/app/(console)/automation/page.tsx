"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, ExternalLink, Github, Play, RefreshCw } from "lucide-react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Section } from "@/components/shared/page";
import { RunStatusPill } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, relativeTime } from "@/lib/format";
import { useIsAdmin } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import type { AutomationSummary, UpstreamStatus } from "@/lib/types";

interface ScheduleResponse {
  local_scheduler: AutomationSummary["scheduler"];
  upstream: UpstreamStatus;
  workflow_runs: { available: boolean; reason?: string; runs: Array<Record<string, string>> };
  publication_mode: string;
  safeguards: string[];
}

export default function AutomationPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const queryClient = useQueryClient();

  const runs = useQuery({
    queryKey: ["automation", 25],
    queryFn: () => api.get<AutomationSummary>("/automation/runs?limit=25"),
    refetchInterval: 30_000,
  });
  const schedule = useQuery({ queryKey: ["automation-schedule"], queryFn: () => api.get<ScheduleResponse>("/automation/schedule") });

  const refresh = useMutation({
    mutationFn: () => api.post("/automation/refresh"),
    onSuccess: () => {
      toast("success", t("automation.triggered"), t("sources.refreshHint"));
      queryClient.invalidateQueries({ queryKey: ["automation"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  if (runs.isLoading) {
    return <SkeletonTable rows={8} />;
  }
  if (runs.isError || !runs.data) {
    return <ErrorState title={t("state.error.title")} detail={(runs.error as Error)?.message} onRetry={() => runs.refetch()} />;
  }

  const data = runs.data;
  const lastRun = data.runs[0];
  const upstream = schedule.data?.upstream;

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("automation.title")}
        subtitle={t("automation.subtitle")}
        actions={
          <Button variant="primary" size="sm" onClick={() => refresh.mutate()} disabled={!isAdmin || refresh.isPending || data.pipeline_in_flight}>
            <Play /> {t("automation.manual")}
          </Button>
        }
      />

      {data.pipeline_in_flight ? <InfoNote tone="info">{t("automation.inFlight")}</InfoNote> : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: t("automation.lastRun"),
            value: lastRun ? formatDateTime(lastRun.started_at, language) : "—",
            hint: lastRun ? `${lastRun.trigger} · ${formatDuration(lastRun.duration_ms)}` : t("automation.empty"),
            icon: CalendarClock,
          },
          {
            label: t("automation.nextRun"),
            value: data.scheduler?.next_run_at ? formatDateTime(data.scheduler.next_run_at, language) : "—",
            hint: t("automation.scheduleApprox"),
            icon: CalendarClock,
          },
          {
            label: t("automation.schedule"),
            value: `${data.scheduler?.interval_minutes ?? "—"} min`,
            hint: data.scheduler?.enabled ? "scheduler enabled" : "scheduler disabled",
            icon: RefreshCw,
          },
          {
            label: t("automation.workflow"),
            value: upstream?.schedule_cron ?? "7 * * * *",
            hint: upstream?.available ? `upstream updated ${relativeTime(upstream.updated_at_utc ?? null, language)}` : t("overview.upstreamUnavailable"),
            icon: Github,
          },
        ].map((item) => (
          <div key={item.label} className="card-surface p-4">
            <div className="flex items-center justify-between">
              <p className="text-[10px] uppercase tracking-[0.14em] text-chalk-500">{item.label}</p>
              <item.icon className="size-3.5 text-chalk-500" />
            </div>
            <p className="mono mt-2 text-[15px] text-chalk-100">{item.value}</p>
            <p className="mt-1 text-[10px] leading-snug text-chalk-500">{item.hint}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Section title={t("automation.runs")} hint={t("automation.scheduleApprox")} className="xl:col-span-2">
          {data.runs.length ? (
            <TableWrap>
              <Table className="min-w-[900px]">
                <thead>
                  <tr>
                    <Th>{t("automation.col.run")}</Th>
                    <Th>{t("common.status")}</Th>
                    <Th>{t("automation.col.trigger")}</Th>
                    <Th>{t("automation.col.started")}</Th>
                    <Th className="text-end">{t("automation.col.duration")}</Th>
                    <Th className="text-end">{t("automation.col.sources")}</Th>
                    <Th className="text-end">{t("automation.col.accepted")}</Th>
                    <Th className="text-end">{t("automation.col.new")}</Th>
                    <Th className="text-end">{t("automation.col.published")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.runs.map((run) => (
                    <Tr key={run.id}>
                      <Td className="mono text-xs text-chalk-100">#{run.id}</Td>
                      <Td>
                        <RunStatusPill status={run.status} />
                      </Td>
                      <Td>
                        <span className="text-[11px] text-chalk-400">{run.trigger}</span>
                      </Td>
                      <Td>
                        <span className="text-[11px] text-chalk-400">{formatDateTime(run.started_at, language)}</span>
                        <span className="block text-[10px] text-chalk-500">{relativeTime(run.started_at, language)}</span>
                      </Td>
                      <Td className="mono text-end text-[11px]">{formatDuration(run.duration_ms)}</Td>
                      <Td className="mono text-end text-[11px]">
                        {run.sources_ok}/{run.sources_total}
                        {run.sources_failed ? <span className="ms-1 text-signal-danger">({run.sources_failed} failed)</span> : null}
                      </Td>
                      <Td className="mono text-end text-[11px] text-neon">{formatNumber(run.accepted, language)}</Td>
                      <Td className="mono text-end text-[11px]">{formatNumber(run.new, language)}</Td>
                      <Td className="text-end text-[10px]">
                        {run.published ? (
                          <Badge tone="success">{t("automation.published")}</Badge>
                        ) : (
                          <Badge tone="muted">{t("automation.skipped")}</Badge>
                        )}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : (
            <EmptyState title={t("automation.empty")} description={t("overview.empty")} />
          )}
        </Section>

        <div className="space-y-4">
          <Section title={t("automation.upstream")} hint={t("overview.schedulerApprox")} padded>
            {upstream?.available ? (
              <div className="space-y-2 text-[11px]">
                <div className="flex items-center justify-between">
                  <span className="text-chalk-500">Published links</span>
                  <span className="mono text-chalk-100">{formatNumber(upstream.total ?? 0, language)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-chalk-500">Workflow updated</span>
                  <span className="mono text-chalk-300">{formatDateTime(upstream.updated_at_utc ?? null, language)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-chalk-500">Cron</span>
                  <span className="mono text-chalk-300">{upstream.schedule_cron}</span>
                </div>
                <div className="space-y-1 pt-1">
                  {(upstream.sources ?? []).slice(0, 4).map((source) => (
                    <div key={source.source} className="flex items-center justify-between gap-2 rounded-lg bg-white/[0.02] px-2 py-1.5">
                      <span className="mono truncate text-[10px] text-chalk-500">{source.source.split("/").slice(-3).join("/")}</span>
                      <Badge tone={source.status === "ok" ? "success" : "danger"}>{source.status}</Badge>
                    </div>
                  ))}
                </div>
                <a
                  href={`https://github.com/${upstream.repo}`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-1 inline-flex items-center gap-1 text-[10px] text-neon hover:underline"
                >
                  {upstream.repo} <ExternalLink className="size-3" />
                </a>
              </div>
            ) : (
              <p className="py-4 text-center text-[11px] text-chalk-500">{t("overview.upstreamUnavailable")}</p>
            )}
          </Section>

          <Section title={t("automation.workflow")} hint={t("automation.workflowUnavailable")} padded>
            {schedule.data?.workflow_runs.available ? (
              <div className="space-y-1.5">
                {schedule.data.workflow_runs.runs.map((run) => (
                  <div key={String(run.id)} className="flex items-center justify-between gap-2 rounded-lg bg-white/[0.02] px-2 py-1.5 text-[10px]">
                    <span className="truncate text-chalk-400">{run.created_at}</span>
                    <Badge tone={run.conclusion === "success" ? "success" : "muted"}>{run.conclusion ?? run.status}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 p-3 text-[10px] leading-relaxed text-chalk-500">
                {schedule.data?.workflow_runs.reason ?? t("automation.workflowUnavailable")}
              </div>
            )}
            <p className="mt-2 text-[10px] leading-relaxed text-chalk-500">
              The existing GitHub Actions workflow remains the authoritative hourly publisher. This console never claims a
              workflow succeeded without a confirmed response.
            </p>
          </Section>

          <Section title={t("automation.errors")} padded>
            {data.error_sources.length ? (
              <div className="space-y-1.5">
                {data.error_sources.map((source) => (
                  <div key={source.id} className="rounded-xl border border-signal-danger/20 bg-signal-danger/[0.05] p-2.5">
                    <p className="flex items-center gap-1.5 text-[11px] text-signal-danger">
                      <AlertTriangle className="size-3" /> {source.name} · {source.consecutive_failures}×
                    </p>
                    <p className="mt-0.5 break-words text-[10px] text-chalk-500">{source.last_error}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-4 text-center text-[11px] text-chalk-500">{t("automation.noErrors")}</p>
            )}
          </Section>
        </div>
      </div>

      {schedule.data?.safeguards.length ? (
        <div className="rounded-2xl border border-white/[0.05] bg-white/[0.015] p-4">
          <p className="mb-2 text-[10px] uppercase tracking-[0.16em] text-chalk-500">Safeguards</p>
          <ul className="grid gap-1.5 sm:grid-cols-3">
            {schedule.data.safeguards.map((item) => (
              <li key={item} className="text-[10px] leading-relaxed text-chalk-500">
                · {item}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
