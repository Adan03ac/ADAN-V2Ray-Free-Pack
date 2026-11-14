"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, ChevronDown, LogOut, Menu, Search, Settings, ShieldAlert, Timer } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import type { AutomationSummary, DashboardSummary, User } from "@/lib/types";

const RANGES = [7, 30, 90] as const;

const TITLES: Record<string, string> = {
  "/": "nav.overview",
  "/sources": "nav.sources",
  "/configurations": "nav.configurations",
  "/health": "nav.health",
  "/subscriptions": "nav.studio",
  "/analytics": "nav.analytics",
  "/automation": "nav.automation",
  "/cloudflare": "nav.cloudflare",
  "/settings": "nav.settings",
};

export function Topbar({ user }: { user: User }) {
  const { t, language } = useT();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const range = useUiStore((state) => state.range);
  const setRange = useUiStore((state) => state.setRange);
  const setSidebarOpen = useUiStore((state) => state.setSidebarOpen);
  const [search, setSearch] = useState("");
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [online, setOnline] = useState(true);
  const alertRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const key = pathname === "/" ? "/" : `/${pathname.split("/")[1]}`;

  const alerts = useQuery({
    queryKey: ["dashboard", range],
    queryFn: () => api.get<DashboardSummary>(`/dashboard/summary?days=${range}`),
    enabled: alertsOpen,
    staleTime: 30_000,
  });
  const automation = useQuery({
    queryKey: ["automation", 1],
    queryFn: () => api.get<AutomationSummary>("/automation/runs?limit=1"),
    staleTime: 60_000,
  });

  const lastRun = automation.data?.runs?.[0];
  const errorSources = alerts.data?.recent_source_errors ?? automation.data?.error_sources ?? [];

  useEffect(() => {
    setOnline(navigator.onLine);
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      if (alertRef.current && !alertRef.current.contains(event.target as Node)) setAlertsOpen(false);
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function logout() {
    try {
      await api.post("/auth/logout");
    } finally {
      queryClient.clear();
      router.replace("/login");
    }
  }

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const term = search.trim();
    router.push(term ? `/configurations?search=${encodeURIComponent(term)}` : "/configurations");
  }

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.05] bg-ink-950/80 backdrop-blur-xl">
      <div className="flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:gap-4 lg:px-7 lg:py-4">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
          >
            <Menu />
          </Button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={cn("size-1.5 rounded-full", online ? "bg-neon" : "bg-signal-danger")} />
              <p className="truncate text-[15px] font-medium tracking-tight text-chalk-100">
                {t(TITLES[key] ?? "nav.overview")}
                <span className="ms-2 hidden text-[11px] font-normal text-chalk-500 sm:inline">
                  {online ? t("topbar.greeting") : t("topbar.offline")}
                </span>
              </p>
            </div>
            <p className="mt-0.5 hidden items-center gap-2 text-[11px] text-chalk-500 sm:flex">
              <Timer className="size-3" />
              {lastRun
                ? `Last run ${formatDateTime(lastRun.started_at, language)} · ${lastRun.accepted.toLocaleString()} accepted`
                : "No ingestion run recorded yet"}
            </p>
          </div>
        </div>

        <form onSubmit={submitSearch} className="relative w-full lg:max-w-[300px]">
          <Search className="pointer-events-none absolute start-3 top-1/2 size-3.5 -translate-y-1/2 text-chalk-500" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("common.searchPlaceholder")}
            aria-label={t("common.search")}
            className="h-9 w-full rounded-full border border-white/[0.07] bg-white/[0.03] ps-9 pe-3 text-xs text-chalk-100 placeholder:text-chalk-500 focus-visible:border-neon/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon/15"
          />
        </form>

        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-full border border-white/[0.07] bg-white/[0.03] p-0.5" title={t("topbar.rangeHelp")}>
            {RANGES.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setRange(value)}
                className={cn(
                  "rounded-full px-2.5 py-1 text-[11px] transition-colors",
                  range === value ? "bg-neon font-medium text-ink-950" : "text-chalk-400 hover:text-chalk-100",
                )}
                aria-pressed={range === value}
              >
                {t(`range.${value}`)}
              </button>
            ))}
          </div>

          <div className="relative" ref={alertRef}>
            <Button
              variant="secondary"
              size="icon"
              onClick={() => setAlertsOpen((open) => !open)}
              aria-label={t("topbar.alerts")}
              aria-expanded={alertsOpen}
            >
              <Bell />
              {errorSources.length > 0 ? (
                <span className="absolute -end-0.5 -top-0.5 grid size-4 place-items-center rounded-full bg-signal-danger font-mono text-[9px] text-ink-950">
                  {errorSources.length}
                </span>
              ) : null}
            </Button>
            {alertsOpen ? (
              <div className="absolute end-0 top-11 w-[min(88vw,340px)] rounded-2xl border border-white/[0.08] bg-ink-800 p-3 shadow-2xl">
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-xs font-medium text-chalk-100">{t("topbar.alerts")}</p>
                  <Badge tone={errorSources.length ? "danger" : "muted"}>{errorSources.length}</Badge>
                </div>
                <p className="mb-2 text-[10px] text-chalk-500">{t("topbar.alertsHint")}</p>
                {alerts.isLoading ? (
                  <p className="py-4 text-center text-[11px] text-chalk-500">{t("common.loading")}</p>
                ) : errorSources.length ? (
                  <ul className="space-y-1.5">
                    {errorSources.map((source) => (
                      <li key={source.id} className="rounded-xl border border-white/[0.05] bg-ink-950/50 p-2.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[11px] text-chalk-300">{source.name}</span>
                          <span className="mono shrink-0 text-[10px] text-signal-danger">{source.consecutive_failures}×</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[10px] text-chalk-500">{source.last_error ?? "unknown error"}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="flex items-center gap-2 rounded-xl bg-white/[0.02] px-3 py-4 text-[11px] text-chalk-500">
                    <ShieldAlert className="size-3.5" /> {t("topbar.noAlerts")}
                  </div>
                )}
                {alerts.isError ? <p className="mt-2 text-[10px] text-signal-danger">{t("state.offline.body")}</p> : null}
              </div>
            ) : null}
          </div>

          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.03] py-1 pe-2 ps-1 transition-colors hover:bg-white/[0.06]"
              aria-expanded={menuOpen}
              aria-label="Account menu"
            >
              <span className="grid size-7 place-items-center rounded-full bg-neon/15 font-mono text-[11px] uppercase text-neon">
                {user.display_name.slice(0, 2)}
              </span>
              <ChevronDown className="size-3.5 text-chalk-500" />
            </button>
            {menuOpen ? (
              <div className="absolute end-0 top-11 w-56 rounded-2xl border border-white/[0.08] bg-ink-800 p-2 shadow-2xl">
                <div className="border-b border-white/[0.06] px-2.5 pb-2.5 pt-1.5">
                  <p className="truncate text-xs text-chalk-100">{user.display_name}</p>
                  <p className="truncate text-[10px] text-chalk-500">{user.email}</p>
                  <Badge tone={user.role === "admin" ? "neon" : "muted"} className="mt-1.5">
                    {user.role === "admin" ? t("common.admin") : t("common.readOnly")}
                  </Badge>
                </div>
                <Link
                  href="/settings"
                  onClick={() => setMenuOpen(false)}
                  className="mt-1 flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-chalk-300 hover:bg-white/[0.05] hover:text-chalk-100"
                >
                  <Settings className="size-3.5" /> {t("nav.settings")}
                </Link>
                <button
                  type="button"
                  onClick={logout}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-start text-xs text-chalk-300 hover:bg-signal-danger/10 hover:text-signal-danger"
                >
                  <LogOut className="size-3.5" /> {t("common.logout")}
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      {!online ? (
        <div className="border-t border-signal-danger/20 bg-signal-danger/[0.08] px-4 py-1.5 text-center text-[11px] text-signal-danger">
          {t("state.offline.title")} — {t("state.offline.body")}
        </div>
      ) : null}
    </header>
  );
}
