"use client";

import { useQuery } from "@tanstack/react-query";
import { CloudOff, ExternalLink, Lock, ShieldAlert } from "lucide-react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Section } from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { SkeletonCard } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { CloudflareStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const CAPABILITY_LABELS: Record<string, string> = {
  worker_deploy: "Worker deployments",
  pages_deploy: "Pages deployments",
  rollback: "Rollback controls",
  secret_management: "Secret management",
  deployment_logs: "Deployment logs",
  account_metrics: "Account metrics",
  bpb_compatibility: "BPB compatibility",
};

export default function CloudflarePage() {
  const { t } = useT();
  const status = useQuery({ queryKey: ["cloudflare"], queryFn: () => api.get<CloudflareStatus>("/cloudflare/status") });

  if (status.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <SkeletonCard key={index} />
        ))}
      </div>
    );
  }

  if (status.isError || !status.data) {
    return <ErrorState title={t("state.error.title")} detail={(status.error as Error)?.message} onRetry={() => status.refetch()} />;
  }

  const data = status.data;

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("cloudflare.title")}
        subtitle={t("cloudflare.subtitle")}
        actions={<Badge tone={data.configured ? "warning" : "muted"}>{data.configured ? "credentials present" : t("cloudflare.notConfigured")}</Badge>}
      />

      <InfoNote tone="warning">{t("cloudflare.honesty")}</InfoNote>

      <div className="grid gap-4 lg:grid-cols-3">
        <Section title={t("cloudflare.status")} padded>
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <span className="grid size-12 place-items-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-chalk-500">
              <CloudOff className="size-6" />
            </span>
            <div>
              <p className="text-sm text-chalk-100">{data.configured ? "Credentials configured" : t("cloudflare.notConfigured")}</p>
              <p className="mx-auto mt-1 max-w-xs text-[11px] leading-relaxed text-chalk-500">{data.message}</p>
            </div>
            <div className="grid w-full grid-cols-2 gap-2 text-[10px]">
              <div className="rounded-lg bg-white/[0.03] px-2 py-1.5">
                <p className="text-chalk-500">account id</p>
                <p className="mono mt-0.5 text-chalk-300">{data.account_id_present ? "present" : "absent"}</p>
              </div>
              <div className="rounded-lg bg-white/[0.03] px-2 py-1.5">
                <p className="text-chalk-500">api token</p>
                <p className="mono mt-0.5 text-chalk-300">{data.token_present ? "present" : "absent"}</p>
              </div>
            </div>
          </div>
        </Section>

        <Section title={t("cloudflare.capabilities")} hint={t("cloudflare.honesty")} className="lg:col-span-2" padded>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {Object.entries(data.capabilities).map(([key, available]) => (
              <li
                key={key}
                className={cn(
                  "flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-[11px]",
                  available ? "border-signal-success/20 bg-signal-success/[0.05] text-chalk-200" : "border-white/[0.05] bg-ink-950/40 text-chalk-400",
                )}
              >
                <span>{CAPABILITY_LABELS[key] ?? key}</span>
                <Badge tone={available ? "success" : "muted"}>{available ? t("cloudflare.available") : t("cloudflare.unavailable")}</Badge>
              </li>
            ))}
          </ul>
          <div className="mt-3 grid grid-cols-2 gap-1.5 text-[10px] text-chalk-500">
            <span className="flex items-center gap-1.5">
              <Lock className="size-3" /> deletions do not clear preview data
            </span>
            <span className="flex items-center gap-1.5">
              <ShieldAlert className="size-3" /> privileged actions require authorization
            </span>
          </div>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={t("cloudflare.planned")} padded>
          <ul className="space-y-1.5">
            {data.planned_capabilities.map((item) => (
              <li key={item} className="flex items-start gap-2 text-[11px] text-chalk-400">
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-violet" />
                {item}
              </li>
            ))}
          </ul>
        </Section>

        <Section title={t("cloudflare.considerations")} padded>
          <ul className="space-y-2">
            {data.considerations.map((item) => (
              <li key={item} className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2 text-[11px] leading-relaxed text-chalk-400">
                {item}
              </li>
            ))}
          </ul>
          <a
            href={data.quota_reference}
            target="_blank"
            rel="noreferrer noopener"
            className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-neon hover:underline"
          >
            Cloudflare Workers limits <ExternalLink className="size-3" />
          </a>
        </Section>
      </div>

      <Section title={t("cloudflare.research")} padded>
        <div className="grid gap-2 sm:grid-cols-3">
          {Object.entries(data.research).map(([key, value]) => (
            <div key={key} className="rounded-xl border border-white/[0.05] bg-ink-950/40 p-3">
              <p className="mono text-[10px] uppercase tracking-wider text-chalk-500">{key}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-chalk-400">{value}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title={t("cloudflare.deployments")} hint={t("cloudflare.noDeployments")}>
        {data.deployments.length ? (
          <div className="p-4 text-xs text-chalk-400">{data.deployments.length} record(s)</div>
        ) : (
          <EmptyState title={t("cloudflare.noDeployments")} description={t("cloudflare.honesty")} icon={<CloudOff className="size-5" />} />
        )}
      </Section>
    </div>
  );
}
