"use client";

import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
  mono = true,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: LucideIcon;
  tone?: "neutral" | "neon" | "violet" | "warning";
  mono?: boolean;
}) {
  const accent = {
    neutral: "text-chalk-300 border-white/[0.07] bg-white/[0.03]",
    neon: "text-neon border-neon/20 bg-neon/[0.07]",
    violet: "text-violet-400 border-violet/25 bg-violet/[0.08]",
    warning: "text-signal-warning border-signal-warning/20 bg-signal-warning/[0.07]",
  }[tone];

  return (
    <div className="card-surface group flex flex-col justify-between gap-3 p-4 transition-colors hover:border-white/[0.09]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-chalk-500">{label}</p>
        {Icon ? (
          <span className={cn("grid size-7 place-items-center rounded-lg border", accent)}>
            <Icon className="size-3.5" />
          </span>
        ) : null}
      </div>
      <div>
        <p className={cn("text-[26px] leading-none text-chalk-100", mono && "mono")}>{value}</p>
        {hint ? <p className="mt-2 text-[11px] leading-snug text-chalk-500">{hint}</p> : null}
      </div>
    </div>
  );
}
