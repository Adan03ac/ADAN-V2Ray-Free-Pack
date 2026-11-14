import type { Language } from "@/lib/i18n";

function intlLocale(language: Language) {
  return language === "fa" ? "fa-IR" : "en-US";
}

export function formatNumber(value: number | null | undefined, language: Language = "en"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(intlLocale(language)).format(value);
}

export function formatCompact(value: number | null | undefined, language: Language = "en"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(intlLocale(language), { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatLatency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(value < 10 ? 2 : 1)} ms`;
}

export function formatDateTime(value: string | null | undefined, language: Language = "en"): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(intlLocale(language), {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatDate(value: string | null | undefined, language: Language = "en"): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(intlLocale(language), { month: "short", day: "2-digit" }).format(date);
}

export function relativeTime(value: string | null | undefined, language: Language = "en"): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(intlLocale(language), { numeric: "auto" });
  const thresholds: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["second", 60],
    ["minute", 60],
    ["hour", 24],
    ["day", 7],
    ["week", 4.35],
    ["month", 12],
  ];
  let duration = diffSeconds;
  for (const [unit, limit] of thresholds) {
    if (Math.abs(duration) < limit) return formatter.format(Math.round(duration), unit);
    duration = duration / limit;
  }
  return formatter.format(Math.round(duration), "year");
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 2 : 1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatPercent(share: number | null | undefined, digits = 1): string {
  if (share === null || share === undefined) return "—";
  return `${(share * 100).toFixed(digits)}%`;
}

export function truncate(value: string, length = 44): string {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}
