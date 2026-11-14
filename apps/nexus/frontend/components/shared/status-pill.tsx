"use client";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";

const CONNECTIVITY: Record<string, { tone: "success" | "warning" | "danger" | "neutral" | "muted" | "violet" | "neon" | "info"; key: string }> = {
  untested: { tone: "muted", key: "health.state.untested" },
  valid_format: { tone: "info", key: "health.state.valid_format" },
  dns_resolved: { tone: "neon", key: "health.state.dns_resolved" },
  reachable: { tone: "success", key: "health.state.reachable" },
  failed: { tone: "danger", key: "health.state.failed" },
  unknown: { tone: "neutral", key: "health.state.unknown" },
  connected: { tone: "violet", key: "health.state.connected" },
};

const RUN: Record<string, { tone: "success" | "warning" | "danger" | "info" | "muted" | "neutral"; label: string }> = {
  succeeded: { tone: "success", label: "Succeeded" },
  ok: { tone: "success", label: "OK" },
  partial: { tone: "warning", label: "Partial" },
  failed: { tone: "danger", label: "Failed" },
  error: { tone: "danger", label: "Error" },
  running: { tone: "info", label: "Running" },
  queued: { tone: "info", label: "Queued" },
  skipped: { tone: "muted", label: "Skipped" },
  not_modified: { tone: "neutral", label: "Not modified" },
  completed: { tone: "success", label: "Completed" },
  valid: { tone: "success", label: "Valid" },
  invalid: { tone: "danger", label: "Invalid" },
};

export function ConnectivityPill({ status }: { status: string }) {
  const { t } = useT();
  const meta = CONNECTIVITY[status] ?? { tone: "neutral" as const, key: "health.state.unknown" };
  const label = CONNECTIVITY[status] ? t(meta.key) : status.replaceAll("_", " ");
  return (
    <Badge tone={meta.tone}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {label}
    </Badge>
  );
}

export function RunStatusPill({ status }: { status: string }) {
  const meta = RUN[status] ?? { tone: "neutral" as const, label: status };
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

export function SourceStatus({ failures, lastSuccess }: { failures: number; lastSuccess: string | null }) {
  const { t } = useT();
  if (failures > 0) return <Badge tone="danger">{t("sources.status.error")}</Badge>;
  if (!lastSuccess) return <Badge tone="muted">{t("sources.status.never")}</Badge>;
  return <Badge tone="success">{t("sources.status.ok")}</Badge>;
}

export function ProtocolTag({ protocol }: { protocol: string }) {
  const tone = protocol === "vless" ? "neon" : protocol === "vmess" ? "violet" : protocol === "trojan" ? "info" : "neutral";
  return (
    <Badge tone={tone} className="font-mono uppercase tracking-wide">
      {protocol}
    </Badge>
  );
}
