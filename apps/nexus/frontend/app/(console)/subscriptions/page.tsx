"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Link2, Plus, QrCode, RefreshCw, Trash2 } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useMemo, useState } from "react";

import { CopyButton } from "@/components/shared/copy-button";
import { EmptyState, ErrorState, InfoNote, PageHeader, Section } from "@/components/shared/page";
import { ConnectivityPill, ProtocolTag } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/toast";
import { api, downloadExport } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useIsAdmin } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import type { SubscriptionProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

const PROTOCOLS = ["vless", "vmess", "trojan", "shadowsocks", "hysteria2"];
const CONNECTIVITY = ["untested", "valid_format", "dns_resolved", "reachable", "failed", "unknown"];

interface PreviewRow {
  id: number;
  protocol: string;
  host: string;
  port: number;
  transport: string;
  security: string;
  connectivity: string;
  latency_ms: number | null;
}

export default function StudioPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [qrOpen, setQrOpen] = useState(false);
  const [generated, setGenerated] = useState<{ url: string; token: string; count: number } | null>(null);

  const [name, setName] = useState("My subscription");
  const [description, setDescription] = useState("");
  const [protocols, setProtocols] = useState<string[]>([]);
  const [connectivity, setConnectivity] = useState<string[]>([]);
  const [maxConfigs, setMaxConfigs] = useState(50);
  const [sort, setSort] = useState("latency_asc");
  const [format, setFormat] = useState("base64");
  const [favoritesOnly, setFavoritesOnly] = useState(false);

  const profiles = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<{ items: SubscriptionProfile[] }>("/subscription-profiles") });
  const selected = useMemo(
    () => profiles.data?.items.find((profile) => profile.id === selectedId) ?? profiles.data?.items[0] ?? null,
    [profiles.data, selectedId],
  );

  useEffect(() => {
    if (selected) {
      setSelectedId(selected.id);
      setName(selected.name);
      setDescription(selected.description ?? "");
      setProtocols(selected.filters.protocols ?? []);
      setConnectivity(selected.filters.connectivity ?? []);
      setMaxConfigs(selected.max_configs);
      setSort(selected.sort);
      setFormat(selected.export_format);
      setFavoritesOnly(selected.favorites_only);
    }
  }, [selected?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const preview = useQuery({
    queryKey: ["profile-preview", selected?.id],
    queryFn: () =>
      api.get<{ preview: PreviewRow[]; returned: number; library_size: number }>(`/subscription-profiles/${selected?.id}/preview`),
    enabled: Boolean(selected?.id),
  });

  function invalidateProfiles() {
    queryClient.invalidateQueries({ queryKey: ["profiles"] });
    queryClient.invalidateQueries({ queryKey: ["profile-preview"] });
  }

  const createProfile = useMutation({
    mutationFn: () =>
      api.post<SubscriptionProfile>("/subscription-profiles", {
        name,
        description: description || null,
        filters: { protocols, connectivity, transports: [], source_ids: [], search: null },
        max_configs: maxConfigs,
        sort,
        export_format: format,
        favorites_only: favoritesOnly,
        exclude_ids: [],
      }),
    onSuccess: (profile) => {
      toast("success", "Profile created", profile.name);
      setCreateOpen(false);
      setSelectedId(profile.id);
      invalidateProfiles();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const updateProfile = useMutation({
    mutationFn: () =>
      api.patch<SubscriptionProfile>(`/subscription-profiles/${selected?.id}`, {
        name,
        description: description || null,
        filters: { protocols, connectivity, transports: [], source_ids: [], search: null },
        max_configs: maxConfigs,
        sort,
        export_format: format,
        favorites_only: favoritesOnly,
      }),
    onSuccess: () => {
      toast("success", t("settings.saved"));
      invalidateProfiles();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const render = useMutation({
    mutationFn: () => api.post<{ url: string; token: string; config_count: number }>(`/subscription-profiles/${selected?.id}/render`),
    onSuccess: (data) => {
      const path = data.url.replace(/^https?:\/\/[^/]+/, "");
      const absolute = `${window.location.origin}${path}`;
      setGenerated({ url: absolute, token: data.token, count: data.config_count });
      toast("success", t("studio.generated"), `${data.config_count} configuration(s)`);
      invalidateProfiles();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const revoke = useMutation({
    mutationFn: (tokenId: number) => api.post(`/subscription-profiles/tokens/${tokenId}/revoke`),
    onSuccess: () => {
      toast("success", t("studio.revoked"));
      invalidateProfiles();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const remove = useMutation({
    mutationFn: () => api.del(`/subscription-profiles/${selected?.id}`),
    onSuccess: () => {
      toast("success", t("studio.deleted"));
      setSelectedId(null);
      setGenerated(null);
      invalidateProfiles();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

  const profilesList = profiles.data?.items ?? [];

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("studio.title")}
        subtitle={t("studio.subtitle")}
        actions={
          <Button variant="primary" size="sm" onClick={() => setCreateOpen(true)} disabled={!isAdmin}>
            <Plus /> {t("studio.new")}
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[320px_1fr]">
        <Section title={t("studio.profiles")} hint={`${profilesList.length} profile(s)`}>
          {profiles.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="skeleton h-16" />
              ))}
            </div>
          ) : profilesList.length ? (
            <ul className="space-y-1.5 p-3">
              {profilesList.map((profile) => (
                <li key={profile.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedId(profile.id);
                      setGenerated(null);
                    }}
                    className={cn(
                      "w-full rounded-2xl border px-3 py-2.5 text-start transition-colors",
                      selected?.id === profile.id
                        ? "border-neon/30 bg-neon/[0.06]"
                        : "border-white/[0.05] bg-ink-950/40 hover:border-white/10",
                    )}
                  >
                    <p className="truncate text-[12px] text-chalk-100">{profile.name}</p>
                    <div className="mt-1 flex items-center justify-between gap-2">
                      <span className="mono text-[10px] text-chalk-500">{profile.export_format}</span>
                      <span className="mono text-[10px] text-chalk-500">
                        {profile.last_config_count !== null ? `${profile.last_config_count} exported` : "not generated"}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title={t("studio.empty")} description={t("studio.unavailable")} />
          )}
        </Section>

        <div className="space-y-4">
          <Section
            title={t("studio.builder")}
            hint={selected ? `${t("studio.name")}: ${selected.name}` : t("studio.new")}
            action={
              selected ? (
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => remove.mutate()} disabled={!isAdmin} aria-label={t("studio.delete")}>
                    <Trash2 />
                  </Button>
                </div>
              ) : null
            }
            padded
          >
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="profile-name">{t("studio.name")}</Label>
                  <Input id="profile-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={120} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profile-desc">Description</Label>
                  <Textarea id="profile-desc" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={1000} className="min-h-[60px]" />
                </div>
                <div className="space-y-1.5">
                  <Label>{t("studio.protocols")}</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {PROTOCOLS.map((protocol) => (
                      <button
                        key={protocol}
                        type="button"
                        onClick={() => setProtocols(toggle(protocols, protocol))}
                        className={cn(
                          "rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors",
                          protocols.includes(protocol)
                            ? "border-neon/40 bg-neon/10 text-neon"
                            : "border-white/10 text-chalk-400 hover:text-chalk-200",
                        )}
                        aria-pressed={protocols.includes(protocol)}
                      >
                        {protocol}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label>{t("studio.connectivity")}</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {CONNECTIVITY.map((state) => (
                      <button
                        key={state}
                        type="button"
                        onClick={() => setConnectivity(toggle(connectivity, state))}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-[10px] transition-colors",
                          connectivity.includes(state)
                            ? "border-violet/40 bg-violet/10 text-violet-400"
                            : "border-white/10 text-chalk-400 hover:text-chalk-200",
                        )}
                        aria-pressed={connectivity.includes(state)}
                      >
                        {state}
                      </button>
                    ))}
                  </div>
                </div>
                <InfoNote tone="info">{t("studio.unavailable")}</InfoNote>
              </div>

              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="max-configs">{t("studio.max")}</Label>
                    <Input
                      id="max-configs"
                      type="number"
                      min={1}
                      max={500}
                      value={maxConfigs}
                      onChange={(event) => setMaxConfigs(Number(event.target.value))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="sort">{t("studio.sort")}</Label>
                    <Select id="sort" value={sort} onChange={(event) => setSort(event.target.value)}>
                      <option value="latency_asc">{t("studio.sort.latency")}</option>
                      <option value="newest">{t("studio.sort.newest")}</option>
                      <option value="recently_seen">{t("studio.sort.seen")}</option>
                      <option value="protocol">{t("studio.sort.protocol")}</option>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="format">{t("studio.format")}</Label>
                  <Select id="format" value={format} onChange={(event) => setFormat(event.target.value)}>
                    <option value="plain">{t("studio.format.plain")}</option>
                    <option value="base64">{t("studio.format.base64")}</option>
                    <option value="json">{t("studio.format.json")}</option>
                  </Select>
                </div>
                <label className="flex items-center justify-between rounded-xl border border-white/[0.06] px-3 py-2.5 text-xs text-chalk-300">
                  {t("studio.favorites")}
                  <Switch checked={favoritesOnly} onCheckedChange={setFavoritesOnly} />
                </label>
                <div className="rounded-xl border border-white/[0.06] bg-ink-950/40 p-3">
                  <p className="text-[10px] uppercase tracking-wider text-chalk-500">{t("studio.matching")}</p>
                  <p className="mono mt-1 text-2xl text-neon">{formatNumber(preview.data?.returned ?? 0, language)}</p>
                  <p className="mt-0.5 text-[10px] text-chalk-500">
                    library {formatNumber(preview.data?.library_size ?? 0, language)} valid configurations
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="primary" size="sm" disabled={!selected || !isAdmin || updateProfile.isPending} onClick={() => updateProfile.mutate()}>
                    {t("common.save")}
                  </Button>
                  <Button variant="outline" size="sm" disabled={!selected || !isAdmin || render.isPending} onClick={() => render.mutate()}>
                    <RefreshCw className={render.isPending ? "animate-spin" : undefined} /> {t("studio.generate")}
                  </Button>
                  {selected ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => downloadExport(selected.id, `adan-nexus-${selected.id}.${format === "json" ? "json" : "txt"}`)}
                    >
                      <Download /> {t("common.download")}
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          </Section>

          {generated ? (
            <Section title={t("studio.generated")} hint={t("studio.tokenNote")} padded>
              <div className="space-y-3">
                <div className="flex flex-col gap-2 rounded-xl border border-neon/20 bg-neon/[0.04] p-3 sm:flex-row sm:items-center">
                  <Link2 className="size-4 shrink-0 text-neon" />
                  <code className="min-w-0 flex-1 break-all font-mono text-[11px] text-chalk-200">{generated.url}</code>
                  <div className="flex gap-1.5">
                    <CopyButton value={generated.url} label={t("studio.copyUrl")} />
                    <Button variant="secondary" size="sm" onClick={() => setQrOpen(true)}>
                      <QrCode /> {t("studio.qr")}
                    </Button>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[10px] text-chalk-500">
                  <Badge tone="neon">{generated.count} entries</Badge>
                  <span className="mono">{generated.token.slice(0, 10)}…</span>
                  <span>{t("studio.lastGenerated")}: {formatDateTime(selected?.last_generated_at ?? null, language)}</span>
                </div>
                <InfoNote tone="warning">{t("studio.tokenNote")}</InfoNote>
              </div>
            </Section>
          ) : null}

          <Section title={t("studio.preview")} hint={`${preview.data?.returned ?? 0} of ${preview.data?.library_size ?? 0}`}>
            {preview.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="skeleton h-10" />
                ))}
              </div>
            ) : preview.data?.preview.length ? (
              <div className="max-h-[320px] overflow-auto">
                <table className="w-full min-w-[600px] text-sm">
                  <thead className="sticky top-0 bg-ink-800">
                    <tr className="border-b border-white/[0.06] text-[10px] uppercase tracking-wider text-chalk-500">
                      <th className="px-4 py-2 text-start font-medium">{t("common.protocol")}</th>
                      <th className="px-3 py-2 text-start font-medium">{t("common.endpoint")}</th>
                      <th className="px-3 py-2 text-start font-medium">{t("configurations.col.connectivity")}</th>
                      <th className="px-4 py-2 text-end font-medium">{t("common.latency")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.data.preview.map((row) => (
                      <tr key={row.id} className="border-b border-white/[0.03]">
                        <td className="px-4 py-2">
                          <ProtocolTag protocol={row.protocol} />
                        </td>
                        <td className="mono px-3 py-2 text-[11px] text-chalk-200">
                          {row.host}:{row.port}
                          <span className="text-chalk-500"> · {row.transport}</span>
                        </td>
                        <td className="px-3 py-2">
                          <ConnectivityPill status={row.connectivity} />
                        </td>
                        <td className="mono px-4 py-2 text-end text-[11px] text-chalk-300">
                          {row.latency_ms !== null ? `${row.latency_ms.toFixed(1)} ms` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title={t("studio.empty")} description={t("studio.unavailable")} />
            )}
          </Section>

          {selected?.tokens.length ? (
            <Section title={t("studio.tokens")} hint={t("studio.tokenNote")} padded>
              <div className="space-y-1.5">
                {selected.tokens.map((token) => (
                  <div key={token.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/[0.05] bg-ink-950/40 p-2.5">
                    <div className="min-w-0">
                      <p className="mono text-[11px] text-chalk-200">{token.token_prefix}•••</p>
                      <p className="text-[10px] text-chalk-500">
                        {token.label} · {token.use_count} uses · created {formatDateTime(token.created_at, language)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={token.revoked_at ? "muted" : "success"}>{token.revoked_at ? "revoked" : "active"}</Badge>
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={!isAdmin || Boolean(token.revoked_at)}
                        onClick={() => revoke.mutate(token.id)}
                      >
                        {t("studio.revoke")}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          ) : null}
        </div>
      </div>

      <Dialog open={createOpen} onOpenChange={(open) => (!open ? setCreateOpen(false) : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("studio.new")}</DialogTitle>
            <DialogDescription>{t("studio.subtitle")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="new-name">{t("studio.name")}</Label>
              <Input id="new-name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="new-format">{t("studio.format")}</Label>
                <Select id="new-format" value={format} onChange={(event) => setFormat(event.target.value)}>
                  <option value="base64">{t("studio.format.base64")}</option>
                  <option value="plain">{t("studio.format.plain")}</option>
                  <option value="json">{t("studio.format.json")}</option>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="new-max">{t("studio.max")}</Label>
                <Input id="new-max" type="number" min={1} max={500} value={maxConfigs} onChange={(event) => setMaxConfigs(Number(event.target.value))} />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreateOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button variant="primary" onClick={() => createProfile.mutate()} disabled={createProfile.isPending || name.trim().length < 2}>
                {t("common.add")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={qrOpen} onOpenChange={(open) => (!open ? setQrOpen(false) : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("studio.qr")}</DialogTitle>
            <DialogDescription>{t("studio.tokenNote")}</DialogDescription>
          </DialogHeader>
          {generated ? (
            <div className="flex flex-col items-center gap-4">
              <div className="rounded-2xl bg-white p-4">
                <QRCodeSVG value={generated.url} size={208} level="M" />
              </div>
              <code className="max-w-full break-all text-center font-mono text-[10px] text-chalk-500">{generated.url}</code>
              <CopyButton value={generated.url} label={t("studio.copyUrl")} />
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
