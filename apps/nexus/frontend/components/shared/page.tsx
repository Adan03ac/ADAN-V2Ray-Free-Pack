"use client";

import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-chalk-100 lg:text-[28px]">{title}</h1>
        {subtitle ? <p className="mt-1.5 max-w-2xl text-sm text-chalk-400">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Section({
  title,
  hint,
  action,
  children,
  className,
  padded = false,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <section className={cn("card-surface flex flex-col", className)}>
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-5">
        <div className="min-w-0">
          <h2 className="text-sm font-medium text-chalk-100">{title}</h2>
          {hint ? <p className="mt-1 text-xs text-chalk-500">{hint}</p> : null}
        </div>
        {action}
      </header>
      <div className={cn("flex-1", padded ? "px-5 pb-5" : "px-0 pb-0")}>{children}</div>
    </section>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  href,
  actionLabel,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  href?: string;
  actionLabel?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="grid size-11 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.03] text-chalk-500">
        {icon ?? <Inbox className="size-5" />}
      </div>
      <div>
        <p className="text-sm font-medium text-chalk-100">{title}</p>
        {description ? <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-chalk-500">{description}</p> : null}
      </div>
      {action}
      {href && actionLabel ? (
        <Button asChild variant="outline" size="sm">
          <Link href={href}>{actionLabel}</Link>
        </Button>
      ) : null}
    </div>
  );
}

export function ErrorState({ title, detail, onRetry }: { title: string; detail?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <div className="grid size-11 place-items-center rounded-2xl border border-signal-danger/25 bg-signal-danger/10 text-signal-danger">
        <AlertCircle className="size-5" />
      </div>
      <div>
        <p className="text-sm font-medium text-chalk-100">{title}</p>
        {detail ? <p className="mx-auto mt-1 max-w-md break-words text-xs text-chalk-500">{detail}</p> : null}
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function InfoNote({ tone = "warning", children }: { tone?: "warning" | "info" | "danger"; children: ReactNode }) {
  const styles = {
    warning: "border-signal-warning/20 bg-signal-warning/[0.06] text-signal-warning",
    info: "border-white/10 bg-white/[0.03] text-chalk-400",
    danger: "border-signal-danger/25 bg-signal-danger/[0.07] text-signal-danger",
  }[tone];
  return (
    <div className={cn("flex items-start gap-2.5 rounded-2xl border px-4 py-3 text-xs leading-relaxed", styles)}>
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <p className="text-chalk-400">{children}</p>
    </div>
  );
}

export function Pagination({
  page,
  pages,
  total,
  onPage,
  label,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
  label: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.05] px-5 py-3 text-xs text-chalk-500">
      <span className="mono">
        {label}: {total}
      </span>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          ‹
        </Button>
        <span className="mono px-1">
          {page} / {Math.max(1, pages)}
        </span>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          ›
        </Button>
      </div>
    </div>
  );
}

export function MonoStat({ children }: { children: ReactNode }) {
  return <span className="mono text-[13px] text-chalk-300">{children}</span>;
}
