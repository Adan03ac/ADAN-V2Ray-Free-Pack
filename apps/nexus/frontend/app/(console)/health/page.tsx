"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Play, ShieldQuestion } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Section } from "@/components/shared/page";
import { ConnectivityPill, RunStatusPill } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { api, queryString } from "@/lib/api";
import { formatDateTime, formatLatency, formatNumber, relativeTime } from "@/lib/format";
import { useIsAdmin } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import type { HealthJob, HealthSummary } from "@/lib/types";

interface HealthTestRow {
  id: number;
  configuration_id: number;
  job_id: number | null;
  status: string;
  stage_reached: string;
  latency_ms: number | null;
  error_category: string | null;
  error_detail: string | null;
  agent_label: string;
  agent_region: string;
  started_at: string;
  finished_at: string | null;
}

const STATES = ["untested", "valid_format", "dns_resolved", "reachable", "failed", "unknown", "connected"];

export default function HealthPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(10);
  const [useTcp, setUseTcp] = useState(true);
  const [useDns, setUseDns] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const summary = useQuery({ queryKey: ["health-summary"], queryFn: () => api.get<HealthSummary>("/health-tests/summary") });
  const jobs = useQuery({
    queryKey: ["health-jobs"],
    queryFn: () => api.get<{ items: HealthJob[]; queue: HealthSummary["queue"] }>("/health-tests/jobs"),
    refetchInterval: 15_000,
  });
  const tests = useQuery({
    queryKey: ["health-tests", statusFilter],
    queryFn: () => api.get<{ items: HealthTestRow[] }>(`/health-tests${queryString({ limit: 30, status: statusFilter })}`),
    refetchInterval: 20_000,
  });

  const start = useMutation({
    mutationFn: () =>
      api.post<{ job: { id: number; total: number }; note: string }>("/health-tests", {
        limit,
        stages: ["syntax", ...(useDns ? ["dns"] : []), ...(useTcp ? ["tcp"] : [])],
        configuration_ids: [],
      }),
    onSuccess: (data) => {
      toast("success", t("health.running"), `Job #${data.job.id} · ${data.job.total} configuration(s)`);
      queryClient.invalidateQueries({ queryKey: ["health-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["health-tests"] });
      queryClient.invalidateQueries({ queryKey: ["health-summary"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const queue = summary.data?.queue ?? jobs.data?.queue;
  const jobsList = jobs.data?.items ?? [];

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader title={t("health.title")} subtitle={t("health.subtitle")} actions={<Badge tone="violet">{summary.data?.agent.label ?? "agent"}</Badge>} />

      <InfoNote tone="warning">{t("health.honesty")}</InfoNote>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: t("health.activeWorkers"), value: queue ? `${queue.active_workers}` : "—", hint: `concurrency ${queue?.concurrency_limit ?? "—"}` },
          { label: t("health.completed"), value: formatNumber(summary.data?.total_jobs ?? 0, language), hint: "jobs recorded" },
          { label: t("health.reachable"), value: formatNumber(jobsList.reduce((sum, job) => sum + job.reachable, 0), language), hint: "TCP connect succeeded" },
          { label: t("health.failed"), value: formatNumber(jobsList.reduce((sum, job) => sum + job.failed, 0), language), hint: "most recent 25 jobs" },
        ].map((item) => (
          <div key={item.label} className="card-surface p-4">
            <p className="text-[10px] uppercase tracking-[0.14em] text-chalk-500">{item.label}</p>
            <p className="mono mt-2 text-2xl text-chalk-100">{item.value}</p>
            <p className="mt-1 text-[10px] text-chalk-500">{item.hint}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Section title={t("health.run")} hint={t("health.form.note")} padded className="xl:col-span-1">
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="limit">{t("health.form.limit")}</Label>
              <Input
                id="limit"
                type="number"
                min={1}
                max={queue?.max_batch ?? 50}
                value={limit}
                onChange={(event) => setLimit(Number(event.target.value))}
              />
              <p className="text-[10px] text-chalk-500">Policy cap: {queue?.max_batch ?? 50} per job. Only registered configurations are eligible.</p>
            </div>
            <div className="space-y-2">
              <Label>{t("health.form.stages")}</Label>
              <label className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-xs text-chalk-300">
                <span className="mono">syntax</span>
                <Switch checked disabled aria-label="syntax stage always enabled" />
              </label>
              <label className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-xs text-chalk-300">
                <span className="mono">dns</span>
                <Switch checked={useDns} onCheckedChange={setUseDns} aria-label="dns stage" />
              </label>
              <label className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-xs text-chalk-300">
                <span className="mono">tcp</span>
                <Switch checked={useTcp} onCheckedChange={setUseTcp} aria-label="tcp stage" />
              </label>
            </div>
            <Button variant="primary" className="w-full" onClick={() => start.mutate()} disabled={!isAdmin || start.isPending}>
              <Play /> {start.isPending ? t("common.loading") : t("health.run")}
            </Button>
            <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 p-3 text-[10px] leading-relaxed text-chalk-500">
              <p className="mb-1 flex items-center gap-1.5 text-chalk-400">
                <ShieldQuestion className="size-3.5" /> {t("health.agent")}
              </p>
              <p className="mono">{summary.data?.agent.label ?? "—"}</p>
              <p>{summary.data?.agent.region ?? "—"}</p>
              <p className="mt-1.5">
                {t("health.timeout")}: {summary.data?.agent.timeout_seconds ?? "—"}s · {t("health.concurrency")}:{" "}
                {summary.data?.agent.concurrency ?? "—"}
              </p>
            </div>
          </div>
        </Section>

        <Section title={t("health.jobs")} hint={t("health.queue")} className="xl:col-span-2">
          {jobs.isLoading ? (
            <SkeletonTable rows={4} />
          ) : jobsList.length ? (
            <TableWrap>
              <Table className="min-w-[820px]">
                <thead>
                  <tr>
                    <Th>Job</Th>
                    <Th>{t("common.status")}</Th>
                    <Th>{t("health.form.stages")}</Th>
                    <Th className="text-end">{t("health.completed")}</Th>
                    <Th className="text-end">{t("health.reachable")}</Th>
                    <Th className="text-end">{t("health.failed")}</Th>
                    <Th>{t("health.agentRegion")}</Th>
                    <Th>{t("common.seen")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {jobsList.map((job) => (
                    <Tr key={job.id}>
                      <Td className="mono text-xs text-chalk-200">#{job.id}</Td>
                      <Td>
                        <RunStatusPill status={job.status} />
                      </Td>
                      <Td>
                        <span className="mono text-[10px] text-chalk-500">{job.stages.join(" → ")}</span>
                      </Td>
                      <Td className="mono text-end text-[11px]">{job.completed}/{job.total}</Td>
                      <Td className="mono text-end text-[11px] text-signal-success">{job.reachable}</Td>
                      <Td className="mono text-end text-[11px] text-signal-danger">{job.failed}</Td>
                      <Td>
                        <span className="text-[10px] text-chalk-500">{job.agent_region}</span>
                      </Td>
                      <Td>
                        <span className="text-[10px] text-chalk-400">{relativeTime(job.requested_at, language)}</span>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : (
            <EmptyState title={t("health.empty")} description={t("health.honesty")} />
          )}
        </Section>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Section title={t("health.legend")} hint={t("health.honesty")} padded>
          <div className="flex flex-wrap gap-2">
            {STATES.map((state) => (
              <ConnectivityPill key={state} status={state} />
            ))}
          </div>
          <div className="mt-4 space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-chalk-500">{t("health.stages")}</p>
            <div className="flex flex-wrap gap-1.5">
              {(summary.data?.stages_implemented ?? []).map((stage) => (
                <Badge key={stage} tone="success">
                  {stage}
                </Badge>
              ))}
            </div>
            <p className="text-[10px] uppercase tracking-wider text-chalk-500">{t("health.stagesUnavailable")}</p>
            <ul className="space-y-1 text-[10px] text-chalk-500">
              {(summary.data?.stages_unavailable ?? []).map((stage) => (
                <li key={stage} className="flex items-start gap-1.5">
                  <span className="mt-1 size-1 shrink-0 rounded-full bg-chalk-500" />
                  {stage}
                </li>
              ))}
            </ul>
          </div>
        </Section>

        <Section title={t("health.breakdown")} padded>
          {summary.data?.breakdown.length ? (
            <ul className="space-y-2">
              {summary.data.breakdown.slice(0, 8).map((item, index) => (
                <li key={`${item.status}-${item.stage}-${index}`} className="flex items-start justify-between gap-2 text-[11px]">
                  <div className="min-w-0">
                    <p className="text-chalk-300">
                      {item.status} <span className="text-chalk-500">/ {item.stage}</span>
                    </p>
                    <p className="mono text-[10px] text-chalk-500">{item.category ?? "no error category"}</p>
                  </div>
                  <span className="mono shrink-0 text-chalk-200">{formatNumber(item.count, language)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-xs text-chalk-500">{t("common.noData")}</p>
          )}
        </Section>

        <Section title={t("health.history")} padded>
          <div className="mb-2 flex items-center justify-between gap-2">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="h-8 w-[160px] text-xs" aria-label={t("common.filter")}>
              <option value="">{t("common.all")}</option>
              {["valid_format", "dns_resolved", "reachable", "failed", "unknown"].map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </Select>
            <span className="mono text-[10px] text-chalk-500">{formatDateTime(summary.data?.last_test_at ?? null, language)}</span>
          </div>
          <div className="max-h-[300px] space-y-1.5 overflow-y-auto pe-1">
            {tests.data?.items.map((test) => (
              <div key={test.id} className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-2.5 py-2">
                <div className="flex items-center justify-between gap-2">
                  <ConnectivityPill status={test.status} />
                  <span className="mono text-[10px] text-chalk-500">cfg #{test.configuration_id}</span>
                </div>
                <div className="mono mt-1 flex items-center justify-between text-[10px] text-chalk-500">
                  <span>{test.error_category ?? test.stage_reached}</span>
                  <span>{test.latency_ms !== null ? formatLatency(test.latency_ms) : "—"}</span>
                </div>
              </div>
            ))}
            {tests.isLoading ? <SkeletonTable rows={3} /> : null}
            {!tests.isLoading && !tests.data?.items.length ? <p className="py-6 text-center text-xs text-chalk-500">{t("health.empty")}</p> : null}
          </div>
        </Section>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-chalk-500">
        <Activity className="size-3.5" /> {t("health.agentNote")}
      </div>
    </div>
  );
}
