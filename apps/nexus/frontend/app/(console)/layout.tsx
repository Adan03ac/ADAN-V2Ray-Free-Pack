"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { api } from "@/lib/api";
import type { AuthMe } from "@/lib/types";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<AuthMe>("/auth/me"),
    retry: false,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (me.isError) router.replace("/login");
  }, [me.isError, router]);

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <span className="grid size-11 animate-pulse place-items-center rounded-2xl bg-neon text-ink-950">
            <Activity className="size-5" />
          </span>
          <div className="space-y-2 text-center">
            <p className="text-sm text-chalk-300">Restoring secure session…</p>
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-chalk-500">ADAN NEXUS · CONNECT</p>
          </div>
        </div>
      </div>
    );
  }

  if (!me.data) return null;

  return <AppShell user={me.data.user}>{children}</AppShell>;
}
