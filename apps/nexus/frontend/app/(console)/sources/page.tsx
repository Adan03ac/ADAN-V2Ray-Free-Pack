"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Pencil, Plus, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Pagination, Section } from "@/components/shared/page";
import { SourceStatus } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { api, ApiError, queryString } from "@/lib/api";
import { formatBytes, formatDateTime, formatDuration, formatNumber, relativeTime } from "@/lib/format";
import { useDebounced, useIsAdmin } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import type { Paginated, Source, SourceDetail } from "@/lib/types";

const SOURCE_TYPES = ["plain_text", "base64", "github_raw", "manual", "html_discovery"];

interface FormState {
  name: string;
  url: string;
  source_type: string;
  trust_level: string;
  refresh_interval_minutes: number;
  tags: string;
  notes: string;
  enabled: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  url: "",
  source_type: "plain_text",
  trust_level: "unknown",
  refresh_interval_minutes: 60,
  tags: "",
  notes: "",
  enabled: true,
};

export default function SourcesPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebounced(search);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Source | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [detailId, setDetailId] = useState<number | null>(null);

  const list = useQuery({
    queryKey: ["sources", debouncedSearch, typeFilter, statusFilter, page],
    queryFn: () =>
      api.get<Paginated<Source> & { supported_types: string[] }>(
        `/sources${queryString({ search: debouncedSearch, source_type: typeFilter, status: statusFilter, page, page_size: 20 })}`,
      ),
  });

  const detail = useQuery({
    queryKey: ["source", detailId],
    queryFn: () => api.get<SourceDetail>(`/sources/${detailId}`),
    enabled: detailId !== null,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["sources"] });
    queryClient.invalidateQueries({ queryKey: ["source"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["automation"] });
  }

  const saveSource = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      editing ? api.patch<Source>(`/sources/${editing.id}`, payload) : api.post<Source>("/sources", payload),
    onSuccess: () => {
      toast("success", editing ? t("sources.form.updated") : t("sources.form.created"));
      setFormOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      invalidate();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const toggleSource = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => api.patch<Source>(`/sources/${id}`, { enabled }),
    onSuccess: () => invalidate(),
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const refreshSource = useMutation({
    mutationFn: (id: number) => api.post(`/sources/${id}/refresh`),
    onSuccess: () => {
      toast("success", t("sources.refreshing"), t("sources.refreshHint"));
      invalidate();
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  }

  function openEdit(source: Source) {
    setEditing(source);
    setForm({
      name: source.name,
      url: source.url,
      source_type: source.source_type,
      trust_level: source.trust_level,
      refresh_interval_minutes: source.refresh_interval_minutes,
      tags: source.tags.join(", "),
      notes: source.notes ?? "",
      enabled: source.enabled,
    });
    setFormOpen(true);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.name.trim() || !form.url.trim()) {
      toast("error", "Validation", "Name and URL are required.");
      return;
    }
    saveSource.mutate({
      name: form.name.trim(),
      url: form.url.trim(),
      source_type: form.source_type,
      trust_level: form.trust_level,
      refresh_interval_minutes: Number(form.refresh_interval_minutes) || 60,
      tags: form.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      notes: form.notes.trim() || null,
      enabled: form.enabled,
    });
  }

  const rows = list.data?.items ?? [];

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("sources.title")}
        subtitle={t("sources.subtitle")}
        actions={
          <Button variant="primary" size="sm" onClick={openCreate} disabled={!isAdmin} title={isAdmin ? undefined : t("common.readOnly")}>
            <Plus /> {t("sources.add")}
          </Button>
        }
      />

      <Section
        title={t("sources.title")}
        hint={t("sources.subtitle")}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute start-3 top-1/2 size-3.5 -translate-y-1/2 text-chalk-500" />
              <Input
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                placeholder={t("sources.searchPlaceholder")}
                className="h-9 w-[220px] ps-9 text-xs"
                aria-label={t("common.search")}
              />
            </div>
            <Select
              value={typeFilter}
              onChange={(event) => {
                setTypeFilter(event.target.value);
                setPage(1);
              }}
              className="h-9 w-[150px] text-xs"
              aria-label={t("sources.filter.type")}
            >
              <option value="">{t("sources.filter.type")}: {t("common.all")}</option>
              {SOURCE_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </Select>
            <Select
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
              className="h-9 w-[140px] text-xs"
              aria-label={t("sources.filter.status")}
            >
              <option value="">{t("sources.filter.status")}: {t("common.all")}</option>
              <option value="ok">{t("sources.status.ok")}</option>
              <option value="error">{t("sources.status.error")}</option>
              <option value="never">{t("sources.status.never")}</option>
            </Select>
          </div>
        }
      >
        {list.isLoading ? (
          <SkeletonTable />
        ) : list.isError ? (
          <ErrorState title={t("state.error.title")} detail={(list.error as Error)?.message} onRetry={() => list.refetch()} />
        ) : !rows.length ? (
          <EmptyState
            title={t("sources.empty")}
            description={t("sources.form.urlHint")}
            action={
              <Button variant="outline" size="sm" onClick={openCreate} disabled={!isAdmin}>
                <Plus /> {t("sources.add")}
              </Button>
            }
          />
        ) : (
          <>
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <Th>{t("sources.col.name")}</Th>
                    <Th>{t("sources.col.type")}</Th>
                    <Th>{t("sources.col.status")}</Th>
                    <Th className="text-end">{t("sources.col.configs")}</Th>
                    <Th>{t("sources.col.lastUpdate")}</Th>
                    <Th className="text-end">{t("sources.col.errors")}</Th>
                    <Th>{t("sources.col.enabled")}</Th>
                    <Th className="text-end">{t("common.actions")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((source) => (
                    <Tr key={source.id}>
                      <Td>
                        <button type="button" onClick={() => setDetailId(source.id)} className="group text-start">
                          <span className="flex items-center gap-2 text-[13px] text-chalk-100 group-hover:text-neon">
                            {source.name}
                            {source.is_discovery ? <Badge tone="violet">discovery</Badge> : null}
                          </span>
                          <span className="mono mt-0.5 block max-w-[320px] truncate text-[10px] text-chalk-500">{source.url}</span>
                        </button>
                      </Td>
                      <Td>
                        <span className="mono text-[11px] text-chalk-400">{source.source_type}</span>
                      </Td>
                      <Td>
                        <SourceStatus failures={source.consecutive_failures} lastSuccess={source.last_success_at} />
                      </Td>
                      <Td className="mono text-end text-[12px] text-chalk-200">
                        {formatNumber(source.config_count, language)}
                        {source.new_config_count ? (
                          <span className="ms-1 text-[10px] text-neon">+{formatNumber(source.new_config_count, language)}</span>
                        ) : null}
                      </Td>
                      <Td>
                        <span className="text-[11px] text-chalk-400">
                          {source.last_success_at ? relativeTime(source.last_success_at, language) : t("common.never")}
                        </span>
                        <span className="mono mt-0.5 block text-[10px] text-chalk-500">
                          HTTP {source.last_http_status ?? "—"}
                          {source.last_duration_ms ? ` · ${formatDuration(source.last_duration_ms)}` : ""}
                        </span>
                      </Td>
                      <Td className="text-end">
                        <span className={source.consecutive_failures ? "mono text-signal-danger" : "mono text-chalk-500"}>
                          {source.consecutive_failures}
                        </span>
                        {source.invalid_count ? (
                          <span className="mono ms-1 text-[10px] text-chalk-500">/ {source.invalid_count} invalid</span>
                        ) : null}
                      </Td>
                      <Td>
                        <Switch
                          checked={source.enabled}
                          disabled={!isAdmin || toggleSource.isPending}
                          onCheckedChange={(checked) => toggleSource.mutate({ id: source.id, enabled: checked })}
                          aria-label={`${t("sources.col.enabled")} ${source.name}`}
                        />
                      </Td>
                      <Td>
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => setDetailId(source.id)} aria-label={t("common.details")}>
                            <Eye />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => refreshSource.mutate(source.id)}
                            disabled={!isAdmin || !source.enabled || refreshSource.isPending}
                            aria-label={t("sources.refresh")}
                            title={source.enabled ? t("sources.refresh") : t("common.disabled")}
                          >
                            <RefreshCw className={refreshSource.isPending ? "animate-spin" : undefined} />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => openEdit(source)} disabled={!isAdmin} aria-label={t("sources.edit")}>
                            <Pencil />
                          </Button>
                        </div>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination
              page={list.data?.page ?? 1}
              pages={list.data?.pages ?? 1}
              total={list.data?.total ?? 0}
              onPage={setPage}
              label={t("common.total")}
            />
          </>
        )}
      </Section>

      <InfoNote tone="info">{t("sources.detail.discoveryNote")}</InfoNote>

      {/* Add / edit dialog */}
      <Dialog open={formOpen} onOpenChange={(open) => (!open ? setFormOpen(false) : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? t("sources.edit") : t("sources.add")}</DialogTitle>
            <DialogDescription>{t("sources.form.urlHint")}</DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-3.5">
            <div className="space-y-1.5">
              <Label htmlFor="source-name">{t("sources.form.name")}</Label>
              <Input id="source-name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required maxLength={200} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="source-url">{t("sources.form.url")}</Label>
              <Input
                id="source-url"
                value={form.url}
                onChange={(event) => setForm({ ...form, url: event.target.value })}
                placeholder="https://example.com/feed.txt"
                required
                inputMode="url"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="source-type">{t("sources.form.type")}</Label>
                <Select id="source-type" value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value })}>
                  {(list.data?.supported_types ?? SOURCE_TYPES).map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="source-trust">{t("sources.form.trust")}</Label>
                <Select id="source-trust" value={form.trust_level} onChange={(event) => setForm({ ...form, trust_level: event.target.value })}>
                  {["trusted", "community", "unknown", "low"].map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="source-interval">{t("sources.form.interval")}</Label>
                <Input
                  id="source-interval"
                  type="number"
                  min={5}
                  max={1440}
                  value={form.refresh_interval_minutes}
                  onChange={(event) => setForm({ ...form, refresh_interval_minutes: Number(event.target.value) })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="source-tags">{t("sources.form.tags")}</Label>
                <Input id="source-tags" value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="github, community" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="source-notes">{t("sources.form.notes")}</Label>
              <Textarea id="source-notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} maxLength={2000} />
            </div>
            <label className="flex items-center gap-2.5 rounded-xl border border-white/[0.06] px-3 py-2.5">
              <Switch checked={form.enabled} onCheckedChange={(checked) => setForm({ ...form, enabled: checked })} />
              <span className="text-xs text-chalk-300">{t("sources.col.enabled")}</span>
            </label>
            <div className="flex justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" variant="primary" disabled={saveSource.isPending}>
                {saveSource.isPending ? t("common.loading") : t("common.save")}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Detail drawer */}
      <Dialog open={detailId !== null} onOpenChange={(open) => (!open ? setDetailId(null) : null)}>
        <DialogContent side="right">
          {detail.isLoading ? (
            <div className="space-y-3">
              <div className="skeleton h-6 w-48" />
              <div className="skeleton h-20 w-full" />
              <div className="skeleton h-40 w-full" />
            </div>
          ) : detail.data ? (
            <div className="space-y-5">
              <DialogHeader>
                <DialogTitle>{detail.data.source.name}</DialogTitle>
                <DialogDescription>
                  <span className="mono">{detail.data.source.url}</span>
                </DialogDescription>
              </DialogHeader>

              <div className="flex flex-wrap items-center gap-2">
                <SourceStatus failures={detail.data.source.consecutive_failures} lastSuccess={detail.data.source.last_success_at} />
                <Badge tone="neutral">{detail.data.source.source_type}</Badge>
                <Badge tone="muted">{detail.data.source.trust_level}</Badge>
                {detail.data.source.is_discovery ? <Badge tone="violet">{t("sources.detail.discovery")}</Badge> : null}
              </div>

              {detail.data.source.last_error ? (
                <div className="rounded-2xl border border-signal-danger/20 bg-signal-danger/[0.06] p-3">
                  <p className="text-[10px] uppercase tracking-wider text-signal-danger">{t("sources.col.errors")}</p>
                  <p className="mt-1 break-words text-xs text-chalk-300">{detail.data.source.last_error}</p>
                </div>
              ) : null}

              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: t("sources.detail.contribution"), value: formatNumber(detail.data.contribution.configurations, language) },
                  { label: "occurrences", value: formatNumber(detail.data.contribution.occurrences, language) },
                  { label: t("sources.detail.http"), value: String(detail.data.source.last_http_status ?? "—") },
                  { label: t("sources.detail.duration"), value: formatDuration(detail.data.source.last_duration_ms) },
                  { label: t("sources.detail.invalid"), value: formatNumber(detail.data.source.invalid_count, language) },
                  { label: t("common.seen"), value: detail.data.source.last_success_at ? relativeTime(detail.data.source.last_success_at, language) : t("common.never") },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                    <p className="text-[9px] uppercase tracking-wider text-chalk-500">{item.label}</p>
                    <p className="mono mt-0.5 text-sm text-chalk-100">{item.value}</p>
                  </div>
                ))}
              </div>

              <div>
                <p className="mb-2 text-xs font-medium text-chalk-200">{t("sources.detail.fetches")}</p>
                <div className="space-y-1.5">
                  {detail.data.fetches.map((fetch) => (
                    <div key={fetch.id} className="rounded-xl border border-white/[0.05] bg-ink-950/40 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <Badge tone={fetch.status === "ok" ? "success" : fetch.status === "error" ? "danger" : "muted"}>{fetch.status}</Badge>
                        <span className="mono text-[10px] text-chalk-500">{formatDateTime(fetch.started_at, language)}</span>
                      </div>
                      <div className="mono mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-chalk-500">
                        <span>HTTP {fetch.http_status ?? "—"}</span>
                        <span>{formatBytes(fetch.bytes_read)}</span>
                        <span>{formatDuration(fetch.duration_ms)}</span>
                        <span>parsed {fetch.parsed_count}</span>
                        <span>accepted {fetch.accepted_count}</span>
                        <span>dup {fetch.duplicate_count}</span>
                        <span>invalid {fetch.invalid_count}</span>
                      </div>
                      {fetch.error ? <p className="mt-1 break-words text-[10px] text-signal-danger">{fetch.error}</p> : null}
                      {fetch.invalid_samples?.length ? (
                        <ul className="mt-1.5 space-y-1">
                          {fetch.invalid_samples.slice(0, 4).map((sample, index) => (
                            <li key={index} className="mono truncate text-[10px] text-chalk-500">
                              {sample.scheme ?? "—"} · {sample.category ?? sample.note} · {sample.reason ?? ""}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ))}
                  {!detail.data.fetches.length ? <p className="text-xs text-chalk-500">{t("common.noData")}</p> : null}
                </div>
              </div>

              <InfoNote tone="info">{t("sources.detail.discoveryNote")}</InfoNote>
            </div>
          ) : (
            <ErrorState title={t("state.error.title")} detail={(detail.error as Error)?.message} onRetry={() => detail.refetch()} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
