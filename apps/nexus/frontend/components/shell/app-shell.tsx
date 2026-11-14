"use client";

import { Sidebar } from "@/components/shell/sidebar";
import { Topbar } from "@/components/shell/topbar";
import type { User } from "@/lib/types";

export function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  return (
    <div className="relative z-10 flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar user={user} />
        <main className="mx-auto w-full max-w-[1560px] flex-1 px-4 py-5 lg:px-7 lg:py-7">{children}</main>
        <footer className="border-t border-white/[0.04] px-4 py-4 text-[10px] text-chalk-500 lg:px-7">
          ADAN NEXUS | CONNECT · Connectivity Intelligence · Public nodes are untrusted; no connectivity guarantee is
          implied. GitHub Actions remains the authoritative public publisher.
        </footer>
      </div>
    </div>
  );
}
