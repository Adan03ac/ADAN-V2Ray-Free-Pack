"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowRight, Globe2, Lock, ShieldCheck, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";

type Mode = "signin" | "register";

export default function LoginPage() {
  const { t, language } = useT();
  const router = useRouter();
  const queryClient = useQueryClient();
  const setLanguage = useUiStore((state) => state.setLanguage);
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setPassword("");
    setConfirm("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (!email.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    if (mode === "register") {
      if (password.length < 10) {
        setError(t("login.weak"));
        return;
      }
      if (password !== confirm) {
        setError(t("login.mismatch"));
        return;
      }
    } else if (password.length < 1) {
      setError("Enter your password.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "signin") {
        await api.post("/auth/login", { email: email.trim().toLowerCase(), password });
      } else {
        await api.post("/auth/register", {
          email: email.trim().toLowerCase(),
          password,
          display_name: displayName.trim() || "Operator",
        });
        toast("success", t("login.created"), t("login.readOnlyNote"));
      }
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : mode === "signin" ? "Sign-in failed" : "Account creation failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="relative z-10 grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden border-e border-white/[0.05] p-10 lg:flex">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-2xl bg-neon text-ink-950">
            <Activity className="size-5" strokeWidth={2.5} />
          </span>
          <div>
            <p className="text-sm font-semibold tracking-tight text-chalk-100">{t("app.name")}</p>
            <p className="font-mono text-[9px] uppercase tracking-[0.32em] text-chalk-500">{t("app.tagline")}</p>
          </div>
        </div>

        <div className="relative max-w-xl">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] text-chalk-400">
            <span className="size-1.5 rounded-full bg-neon" /> Connectivity Intelligence Command Center
          </div>
          <h1 className="text-[44px] font-semibold leading-[1.05] tracking-[-0.03em] text-chalk-100">
            Source registry.
            <br />
            Provenance.
            <br />
            <span className="text-neon">Reachability.</span>
          </h1>
          <p className="mt-5 max-w-md text-sm leading-relaxed text-chalk-400">{t("login.brandNote")}</p>

          <div className="mt-10 grid max-w-md grid-cols-2 gap-3">
            {[
              { icon: ShieldCheck, label: "RBAC + audit trail", note: "Admin and read-only roles" },
              { icon: Globe2, label: "SSRF-hardened ingest", note: "HTTPS, conditional GET" },
              { icon: Lock, label: "Encrypted secrets", note: "Share links never returned" },
              { icon: Activity, label: "Honest telemetry", note: "No synthesized metrics" },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl border border-white/[0.06] bg-ink-850/60 p-3.5">
                <item.icon className="size-4 text-neon" />
                <p className="mt-2 text-xs text-chalk-200">{item.label}</p>
                <p className="mt-0.5 text-[10px] text-chalk-500">{item.note}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[10px] leading-relaxed text-chalk-500">
          Public subscription feeds are untrusted. Reachability is not proof of a working tunnel. No unlimited bandwidth
          or guaranteed access is promised.
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-12">
        <div className="w-full max-w-[380px]">
          <div className="mb-8 flex items-center justify-between">
            <div className="flex items-center gap-2 lg:hidden">
              <span className="grid size-8 place-items-center rounded-xl bg-neon text-ink-950">
                <Activity className="size-4" />
              </span>
              <span className="text-sm font-semibold text-chalk-100">{t("app.name")}</span>
            </div>
            <button
              type="button"
              onClick={() => setLanguage(language === "en" ? "fa" : "en")}
              className="ms-auto rounded-full border border-white/[0.08] px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-chalk-400 hover:text-neon"
            >
              {language === "en" ? "فارسی" : "English"}
            </button>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight text-chalk-100">
            {mode === "signin" ? t("login.title") : t("login.createTitle")}
          </h2>
          <p className="mt-1.5 text-sm text-chalk-400">
            {mode === "signin" ? t("login.subtitle") : t("login.createSubtitle")}
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            {mode === "register" ? (
              <div className="space-y-1.5">
                <Label htmlFor="display-name">{t("login.displayName")}</Label>
                <Input
                  id="display-name"
                  autoComplete="name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  placeholder="Nexus Operator"
                  maxLength={120}
                />
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="email">{t("login.email")}</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="operator@adan.local"
                required
                aria-invalid={Boolean(error)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••••"
                required
                minLength={mode === "register" ? 10 : undefined}
                aria-invalid={Boolean(error)}
              />
              {mode === "register" ? (
                <p className="text-[10px] text-chalk-500">Minimum 10 characters. Stored with bcrypt, never logged.</p>
              ) : null}
            </div>

            {mode === "register" ? (
              <div className="space-y-1.5">
                <Label htmlFor="confirm">{t("login.confirm")}</Label>
                <Input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  placeholder="••••••••••"
                  required
                  minLength={10}
                  aria-invalid={Boolean(error)}
                />
              </div>
            ) : null}

            {error ? (
              <div role="alert" className="rounded-xl border border-signal-danger/25 bg-signal-danger/[0.08] px-3 py-2 text-xs text-signal-danger">
                {mode === "signin" ? `${t("login.failed")}: ` : ""}
                {error}
              </div>
            ) : null}

            <Button type="submit" variant="primary" size="lg" className="w-full" disabled={submitting}>
              {submitting
                ? mode === "signin"
                  ? t("login.submitting")
                  : t("login.creating")
                : mode === "signin"
                  ? t("login.submit")
                  : t("login.create")}
              <ArrowRight />
            </Button>

            {mode === "signin" ? (
              <Button type="button" variant="secondary" size="lg" className="w-full" onClick={() => switchMode("register")} disabled={submitting}>
                <UserPlus /> {t("login.createLink")}
              </Button>
            ) : (
              <Button type="button" variant="ghost" className="w-full" onClick={() => switchMode("signin")} disabled={submitting}>
                {t("login.haveAccount")} {t("login.signInLink")}
              </Button>
            )}
          </form>

          {mode === "register" ? (
            <p className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[10px] leading-relaxed text-chalk-500">
              {t("login.readOnlyNote")}
            </p>
          ) : null}

          <p className="mt-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[10px] leading-relaxed text-chalk-500">
            {t("login.security")}
          </p>
          <p className="mt-3 text-[10px] leading-relaxed text-chalk-500">{t("login.bootstrap")}</p>
        </div>
      </section>
    </div>
  );
}
