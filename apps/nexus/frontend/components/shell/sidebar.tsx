"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  Boxes,
  Cloud,
  Gauge,
  LayoutDashboard,
  Radio,
  Settings,
  SlidersHorizontal,
  Workflow,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { RunStatusPill } from "@/components/shared/status-pill";
import { api } from "@/lib/api";
import { formatNumber, relativeTime } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { AutomationSummary } from "@/lib/types";

const NAV = [
  { href: "/", key: "nav.overview", icon: LayoutDashboard, section: "operations" },
  { href: "/sources", key: "nav.sources", icon: Radio, section: "operations" },
  { href: "/configurations", key: "nav.configurations", icon: Boxes, section: "operations" },
  { href: "/health", key: "nav.health", icon: Gauge, section: "operations" },
  { href: "/subscriptions", key: "nav.studio", icon: SlidersHorizontal, section: "intelligence" },
  { href: "/analytics", key: "nav.analytics", icon: BarChart3, section: "intelligence" },
  { href: "/automation", key: "nav.automation", icon: Workflow, section: "platform" },
  { href: "/cloudflare", key: "nav.cloudflare", icon: Cloud, section: "platform" },
  { href: "/settings", key: "nav.settings", icon: Settings, section: "platform" },
] as const;

const SECTIONS = ["operations", "intelligence", "platform"] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { t, language } = useT();
  const sidebarOpen = useUiStore((state) => state.sidebarOpen);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);

  const automation = useQuery({
    queryKey: ["automation", 1],
    queryFn: () => api.get<AutomationSummary>("/automation/runs?limit=1"),
    refetchInterval: 60_000,
  });
  const lastRun = automation.data?.runs?.[0];
  const errorCount = automation.data?.error_sources?.length ?? 0;
  const enabled = automation.data?.enabled_sources ?? 0;

  return (
    <>
      {sidebarOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-ink-950/70 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}
      <aside
        className={cn(
          "fixed inset-y-0 start-0 z-50 flex w-[256px] flex-col border-e border-white/[0.06] bg-[#0A0C0D]/95 px-4 pb-4 pt-5 backdrop-blur-xl transition-transform duration-200 lg:static lg:z-0 lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full lg:rtl:translate-x-0",
        )}
      >
        <div className="mb-7 flex items-center justify-between px-1">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-xl bg-neon text-ink-950 shadow-[0_0_30px_-8px_rgba(157,255,0,0.55)]">
              <Activity className="size-5" strokeWidth={2.5} />
            </span>
            <span className="leading-tight">
              <span className="block text-[15px] font-semibold tracking-tight text-chalk-100">{t("app.name")}</span>
              <span className="block font-mono text-[9px] uppercase tracking-[0.28em] text-chalk-500">{t("app.suffix")}</span>
            </span>
          </Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-1.5 text-chalk-500 hover:bg-white/5 hover:text-chalk-100 lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto pb-2">
          {SECTIONS.map((section) => (
            <div key={section}>
              <p className="px-2 pb-1.5 text-[9px] font-medium uppercase tracking-[0.2em] text-chalk-500/70">
                {t(`nav.section.${section}`)}
              </p>
              <ul className="space-y-0.5">
                {NAV.filter((item) => item.section === section).map((item) => {
                  const Icon = item.icon;
                  const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setSidebarOpen(false)}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] transition-colors",
                          active
                            ? "bg-neon font-medium text-ink-950 shadow-[0_8px_24px_-16px_rgba(157,255,0,0.9)]"
                            : "text-chalk-400 hover:bg-white/[0.04] hover:text-chalk-100",
                        )}
                        aria-current={active ? "page" : undefined}
                      >
                        <Icon className={cn("size-4", active ? "text-ink-950" : "text-chalk-500 group-hover:text-chalk-300")} />
                        <span className="truncate">{t(item.key)}</span>
                        {item.href === "/sources" && errorCount > 0 ? (
                          <span className="ms-auto rounded-full bg-signal-danger/20 px-1.5 py-0.5 font-mono text-[10px] text-signal-danger">
                            {errorCount}
                          </span>
                        ) : null}
                        {item.href === "/automation" && lastRun?.status === "running" ? (
                          <span className="ms-auto size-1.5 animate-pulse rounded-full bg-signal-info" />
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="mt-3 rounded-2xl border border-white/[0.07] bg-ink-850 p-3.5">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-chalk-500">Public bank</p>
            <span className="flex items-center gap-1.5 text-[10px] text-chalk-500">
              <span className={cn("size-1.5 rounded-full", automation.isError ? "bg-signal-danger" : "bg-neon")} />
              {automation.isError ? t("topbar.offline") : t("topbar.live")}
            </span>
          </div>
          <p className="mt-2 text-lg leading-none text-chalk-100">
            <span className="mono">{formatNumber(enabled, language)}</span>
            <span className="ms-1.5 text-[11px] text-chalk-500">sources</span>
          </p>
          <div className="mt-2.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-neon transition-all"
              style={{ width: `${Math.min(100, Math.max(8, (lastRun?.accepted ?? 0) / 120))}%` }}
            />
          </div>
          <div className="mt-2.5 flex items-center justify-between gap-2">
            {lastRun ? <RunStatusPill status={lastRun.status} /> : <span className="text-[10px] text-chalk-500">No runs</span>}
            <span className="truncate text-[10px] text-chalk-500">
              {lastRun ? relativeTime(lastRun.started_at, language) : "—"}
            </span>
          </div>
          <Link
            href="/automation"
            className="mt-2.5 block w-full rounded-lg border border-white/[0.08] py-1.5 text-center text-[11px] text-chalk-300 transition-colors hover:border-neon/30 hover:text-neon"
          >
            {t("automation.schedule")}
          </Link>
        </div>
      </aside>
    </>
  );
}
