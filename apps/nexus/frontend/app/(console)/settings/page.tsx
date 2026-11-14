"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, KeyRound, Languages, ShieldCheck, UserPlus } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Section } from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useIsAdmin, useMe } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/lib/store";
import type { AuditEntry, User } from "@/lib/types";

interface SystemSettings {
  items: Array<{ key: string; value: Record<string, unknown>; updated_at: string }>;
  runtime: Record<string, string | number | boolean | null>;
  capabilities: {
    subscription_formats: string[];
    health_stages: string[];
    cloudflare_deployments: boolean;
    end_to_end_verification: boolean;
    iran_testing_agent: boolean;
  };
}

export default function SettingsPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const me = useMe();
  const queryClient = useQueryClient();
  const setLanguage = useUiStore((state) => state.setLanguage);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("read_only");

  const settings = useQuery({ queryKey: ["system-settings"], queryFn: () => api.get<SystemSettings>("/system/settings") });
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<User[]>("/auth/users"), enabled: isAdmin });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => api.get<{ items: AuditEntry[] }>("/system/audit-logs?limit=30"), enabled: isAdmin });

  const createUser = useMutation({
    mutationFn: () => api.post<User>("/auth/users", { email, password, display_name: displayName || "Operator", role }),
    onSuccess: () => {
      toast("success", t("settings.userCreated"), email);
      setEmail("");
      setPassword("");
      setDisplayName("");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const updateUser = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { role?: string; is_active?: boolean } }) =>
      api.patch<User>(`/auth/users/${id}`, payload),
    onSuccess: () => {
      toast("success", t("settings.roleUpdated"));
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const savePreference = useMutation({
    mutationFn: (payload: { key: string; value: Record<string, unknown> }) => api.patch("/system/settings", payload),
    onSuccess: () => {
      toast("success", t("settings.saved"));
      queryClient.invalidateQueries({ queryKey: ["system-settings"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  function changeLanguage(next: "en" | "fa") {
    setLanguage(next);
    if (isAdmin) savePreference.mutate({ key: "ui", value: { default_language: next } });
  }

  if (settings.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-52" />
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-64 rounded-3xl" />
          <Skeleton className="h-64 rounded-3xl" />
        </div>
      </div>
    );
  }

  if (settings.isError || !settings.data) {
    return <ErrorState title={t("state.error.title")} detail={(settings.error as Error)?.message} onRetry={() => settings.refetch()} />;
  }

  const runtime = settings.data.runtime;

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
        actions={<Badge tone={me.data?.user.role === "admin" ? "neon" : "muted"}>{me.data?.user.role === "admin" ? t("common.admin") : t("common.readOnly")}</Badge>}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={t("settings.account")} padded>
          <div className="space-y-3">
            <div className="flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-ink-950/40 p-3">
              <span className="grid size-10 place-items-center rounded-full bg-neon/15 font-mono text-sm uppercase text-neon">
                {(me.data?.user.display_name ?? "op").slice(0, 2)}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm text-chalk-100">{me.data?.user.display_name}</p>
                <p className="truncate text-[11px] text-chalk-500">{me.data?.user.email}</p>
              </div>
              <Badge tone="muted" className="ms-auto shrink-0">
                {me.data?.user.role}
              </Badge>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-chalk-500">{t("settings.expires")}</p>
                <p className="mono mt-0.5 text-chalk-200">{formatDateTime(me.data?.expires_at ?? null, language)}</p>
              </div>
              <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-chalk-500">Last login</p>
                <p className="mono mt-0.5 text-chalk-200">{formatDateTime(me.data?.user.last_login_at ?? null, language)}</p>
              </div>
            </div>
            <div className="flex items-start gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-[10px] leading-relaxed text-chalk-500">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-signal-success" />
              <span>
                HttpOnly session cookie, CSRF double-submit, per-IP login rate limiting, account lockout after repeated
                failures. Password changes are not exposed in this build; rotate the bootstrap secret and recreate the
                account instead.
              </span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                await api.post("/auth/logout");
                window.location.href = "/login";
              }}
            >
              {t("settings.logout")}
            </Button>
          </div>
        </Section>

        <Section title={t("settings.preferences")} padded>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label className="flex items-center gap-1.5">
                <Languages className="size-3.5" /> {t("settings.language")}
              </Label>
              <div className="grid grid-cols-2 gap-2">
                {(["en", "fa"] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => changeLanguage(value)}
                    className={`rounded-xl border px-3 py-2.5 text-sm transition-colors ${
                      language === value ? "border-neon/40 bg-neon/[0.07] text-neon" : "border-white/[0.07] text-chalk-400 hover:text-chalk-100"
                    }`}
                    aria-pressed={language === value}
                  >
                    {value === "en" ? "English" : "فارسی"}
                  </button>
                ))}
              </div>
              <p className="text-[10px] text-chalk-500">
                Persian switches the document to RTL with dedicated typography. {t("settings.storageNote")}
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>{t("settings.theme")}</Label>
              <div className="rounded-xl border border-white/[0.07] px-3 py-2.5 text-sm text-chalk-300">{t("settings.themeDark")}</div>
              <p className="text-[10px] text-chalk-500">A single reference-matched palette is shipped; no alternate theme is offered.</p>
            </div>
          </div>
        </Section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title={t("settings.capabilities")} hint={t("settings.subtitle")} padded>
          <div className="space-y-2 text-[11px]">
            <div className="flex flex-wrap gap-1.5">
              {settings.data.capabilities.subscription_formats.map((format) => (
                <Badge key={format} tone="success">
                  {format}
                </Badge>
              ))}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {settings.data.capabilities.health_stages.map((stage) => (
                <Badge key={stage} tone="violet">
                  {stage}
                </Badge>
              ))}
            </div>
            <div className="space-y-1 pt-1">
              {[
                { label: "Cloudflare deployments", value: settings.data.capabilities.cloudflare_deployments },
                { label: "End-to-end verification", value: settings.data.capabilities.end_to_end_verification },
                { label: "Iran testing agent", value: settings.data.capabilities.iran_testing_agent },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between rounded-lg bg-white/[0.02] px-2.5 py-1.5">
                  <span className="text-chalk-400">{item.label}</span>
                  <Badge tone={item.value ? "success" : "muted"}>{item.value ? t("cloudflare.available") : t("overview.verificationOff")}</Badge>
                </div>
              ))}
            </div>
          </div>
        </Section>

        <Section title={t("settings.runtime")} hint={t("settings.storageNote")} padded>
          <dl className="space-y-1.5 text-[11px]">
            {Object.entries(runtime).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between gap-2 rounded-lg bg-white/[0.02] px-2.5 py-1.5">
                <dt className="truncate text-chalk-500">{key.replaceAll("_", " ")}</dt>
                <dd className="mono shrink-0 text-chalk-200">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>

      <Section title={t("settings.retention")} hint={t("settings.storageNote")} padded>
        <div className="grid gap-2 sm:grid-cols-3">
          {Object.entries(settings.data.items.find((item) => item.key === "retention")?.value ?? {}).map(([key, value]) => (
            <div key={key} className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
              <p className="text-[9px] uppercase tracking-wider text-chalk-500">{key.replaceAll("_", " ")}</p>
              <p className="mono mt-0.5 text-sm text-chalk-100">{formatNumber(Number(value), language)}</p>
            </div>
          ))}
        </div>
        <InfoNote tone="info">
          Retention windows are applied after every pipeline run. Environment variables remain authoritative over stored
          preferences.
        </InfoNote>
      </Section>

      {isAdmin ? (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title={t("settings.users")} hint={`${users.data?.length ?? 0} operator(s)`} padded>
              <div className="space-y-1.5">
                {(users.data ?? []).map((user) => {
                  const isSelf = user.id === me.data?.user.id;
                  return (
                    <div key={user.id} className="flex items-center justify-between gap-2 rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[11px] text-chalk-200">
                          {user.display_name}
                          {isSelf ? <span className="ms-1.5 text-[9px] text-chalk-500">({t("settings.you")})</span> : null}
                        </p>
                        <p className="truncate text-[10px] text-chalk-500">{user.email}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {isSelf ? (
                          <Badge tone={user.role === "admin" ? "neon" : "muted"}>{user.role}</Badge>
                        ) : (
                          <>
                            <Select
                              value={user.role}
                              aria-label={`${t("settings.role")} ${user.email}`}
                              onChange={(event) => updateUser.mutate({ id: user.id, payload: { role: event.target.value } })}
                              className="h-8 w-[112px] text-[11px]"
                              disabled={updateUser.isPending}
                            >
                              <option value="read_only">{t("settings.readOnly")}</option>
                              <option value="admin">{t("settings.adminUser")}</option>
                            </Select>
                            <Switch
                              checked={user.is_active}
                              aria-label={`${t("common.enabled")} ${user.email}`}
                              disabled={updateUser.isPending}
                              onCheckedChange={(checked) => updateUser.mutate({ id: user.id, payload: { is_active: checked } })}
                            />
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!email.includes("@") || password.length < 10) {
                    toast("error", "Validation", "A valid email and a password of at least 10 characters are required.");
                    return;
                  }
                  createUser.mutate();
                }}
                className="mt-3 space-y-2 rounded-xl border border-white/[0.06] p-3"
              >
                <p className="flex items-center gap-1.5 text-[11px] text-chalk-300">
                  <UserPlus className="size-3.5" /> {t("settings.addUser")}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("settings.email")} type="email" className="h-9 text-xs" required />
                  <Input
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    placeholder={t("settings.displayName")}
                    className="h-9 text-xs"
                  />
                  <Input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={`${t("settings.password")} (min 10)`}
                    type="password"
                    className="h-9 text-xs"
                    required
                    minLength={10}
                  />
                  <Select value={role} onChange={(event) => setRole(event.target.value)} className="h-9 text-xs" aria-label={t("settings.role")}>
                    <option value="read_only">{t("settings.readOnly")}</option>
                    <option value="admin">{t("settings.adminUser")}</option>
                  </Select>
                </div>
                <Button type="submit" variant="secondary" size="sm" disabled={createUser.isPending}>
                  <KeyRound /> {t("settings.addUser")}
                </Button>
              </form>
            </Section>

            <Section title={t("settings.api")} padded>
              <div className="space-y-2 text-[11px]">
                <a href="/api/docs" target="_blank" rel="noreferrer noopener" className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-chalk-300 hover:text-neon">
                  {t("settings.apiDocs")} <ExternalLink className="size-3" />
                </a>
                <a href="/api/openapi.json" target="_blank" rel="noreferrer noopener" className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-chalk-300 hover:text-neon">
                  OpenAPI schema <ExternalLink className="size-3" />
                </a>
                <a href="/api/v1/system/health" target="_blank" rel="noreferrer noopener" className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2 text-chalk-300 hover:text-neon">
                  Health endpoint <ExternalLink className="size-3" />
                </a>
                <p className="pt-1 leading-relaxed text-chalk-500">
                  Mutating endpoints require a session cookie, an administrator role and a matching CSRF header. Tokens
                  for public subscriptions are hashed at rest and revocable.
                </p>
              </div>
            </Section>
          </div>

          <Section title={t("settings.audit")} hint={`${audit.data?.items.length ?? 0} recent entries`}>
            {audit.isLoading ? (
              <div className="p-4">
                <Skeleton className="h-24" />
              </div>
            ) : audit.data?.items.length ? (
              <TableWrap>
                <Table className="min-w-[760px]">
                  <thead>
                    <tr>
                      <Th>#</Th>
                      <Th>Action</Th>
                      <Th>Actor</Th>
                      <Th>Target</Th>
                      <Th>Outcome</Th>
                      <Th>IP</Th>
                      <Th>When</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.data.items.map((entry) => (
                      <Tr key={entry.id}>
                        <Td className="mono text-[10px] text-chalk-500">{entry.id}</Td>
                        <Td className="mono text-[11px] text-chalk-200">{entry.action}</Td>
                        <Td className="text-[11px] text-chalk-400">{entry.actor ?? "anonymous"}</Td>
                        <Td className="mono text-[10px] text-chalk-500">
                          {entry.target_type ?? "—"}
                          {entry.target_id ? ` #${entry.target_id}` : ""}
                        </Td>
                        <Td>
                          <Badge tone={entry.outcome === "success" ? "success" : entry.outcome === "failure" ? "danger" : "warning"}>
                            {entry.outcome}
                          </Badge>
                        </Td>
                        <Td className="mono text-[10px] text-chalk-500">{entry.ip_address ?? "—"}</Td>
                        <Td className="text-[10px] text-chalk-400">{formatDateTime(entry.created_at, language)}</Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            ) : (
              <EmptyState title={t("settings.noAudit")} />
            )}
          </Section>
        </>
      ) : null}
    </div>
  );
}
