"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Search, Star } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, InfoNote, PageHeader, Pagination, Section } from "@/components/shared/page";
import { ConnectivityPill, ProtocolTag } from "@/components/shared/status-pill";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SkeletonTable } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { api, queryString } from "@/lib/api";
import { formatDateTime, formatLatency, formatNumber, relativeTime } from "@/lib/format";
import { useDebounced, useIsAdmin } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import type { ConfigurationDetail, ConfigurationRow, Paginated } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Facets {
  protocols: Array<{ value: string; count: number }>;
  transports: Array<{ value: string; count: number }>;
  connectivity: Array<{ value: string; count: number }>;
  sources: Array<{ id: number; name: string }>;
}

export default function ConfigurationsPage() {
  const { t, language } = useT();
  const isAdmin = useIsAdmin();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [protocol, setProtocol] = useState("");
  const [connectivity, setConnectivity] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [transport, setTransport] = useState("");
  const [favorites, setFavorites] = useState(false);
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [note, setNote] = useState("");

  const debouncedSearch = useDebounced(search);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("search");
    if (initial) setSearch(initial);
  }, []);

  const facets = useQuery({ queryKey: ["configuration-facets"], queryFn: () => api.get<Facets>("/configurations/facets") });

  const list = useQuery({
    queryKey: ["configurations", debouncedSearch, protocol, connectivity, sourceId, transport, favorites, sort, page],
    queryFn: () =>
      api.get<Paginated<ConfigurationRow>>(
        `/configurations${queryString({
          search: debouncedSearch,
          protocol,
          connectivity,
          source_id: sourceId,
          transport,
          favorites: favorites ? true : undefined,
          sort,
          page,
          page_size: 25,
        })}`,
      ),
  });

  const detail = useQuery({
    queryKey: ["configuration", detailId],
    queryFn: () => api.get<ConfigurationDetail>(`/configurations/${detailId}`),
    enabled: detailId !== null,
  });

  useEffect(() => {
    if (detail.data) setNote(detail.data.notes ?? "");
  }, [detail.data]);

  const bulkFavorite = useMutation({
    mutationFn: ({ ids, favorite }: { ids: number[]; favorite: boolean }) =>
      api.post<{ updated: number }>("/configurations/bulk-favorite", { ids, favorite }),
    onSuccess: (result, variables) => {
      toast("success", variables.favorite ? "Favorites updated" : "Favorites removed", `${result.updated} configuration(s)`);
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["configurations"] });
      queryClient.invalidateQueries({ queryKey: ["configuration"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const saveNote = useMutation({
    mutationFn: (payload: { notes?: string; is_favorite?: boolean }) => api.patch(`/configurations/${detailId}`, payload),
    onSuccess: () => {
      toast("success", t("configurations.detail.saved"));
      queryClient.invalidateQueries({ queryKey: ["configurations"] });
      queryClient.invalidateQueries({ queryKey: ["configuration"] });
    },
    onError: (error: Error) => toast("error", t("common.error"), error.message),
  });

  const rows = list.data?.items ?? [];
  const allSelected = useMemo(() => rows.length > 0 && rows.every((row) => selected.includes(row.id)), [rows, selected]);

  function toggleAll(checked: boolean) {
    setSelected(checked ? rows.map((row) => row.id) : []);
  }

  function toggleOne(id: number, checked: boolean) {
    setSelected((current) => (checked ? [...new Set([...current, id])] : current.filter((value) => value !== id)));
  }

  const activeFilters = [protocol, connectivity, sourceId, transport, favorites ? "fav" : "", debouncedSearch].filter(Boolean).length;

  return (
    <div className="space-y-4 animate-fade-up">
      <PageHeader
        title={t("configurations.title")}
        subtitle={t("configurations.subtitle")}
        actions={
          selected.length ? (
            <>
              <span className="mono text-[11px] text-chalk-500">
                {selected.length} {t("configurations.selected")}
              </span>
              <Button variant="secondary" size="sm" disabled={!isAdmin || bulkFavorite.isPending} onClick={() => bulkFavorite.mutate({ ids: selected, favorite: true })}>
                <Star /> {t("configurations.bulkFavorite")}
              </Button>
              <Button variant="ghost" size="sm" disabled={!isAdmin || bulkFavorite.isPending} onClick={() => bulkFavorite.mutate({ ids: selected, favorite: false })}>
                {t("configurations.bulkUnfavorite")}
              </Button>
            </>
          ) : (
            <Badge tone="muted">{t("configurations.detail.credentials")}</Badge>
          )
        }
      />

      <Section
        title={t("configurations.title")}
        hint={activeFilters ? `${activeFilters} filter(s) active` : t("configurations.search")}
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
                placeholder={t("configurations.search")}
                className="h-9 w-[230px] ps-9 text-xs"
                aria-label={t("common.search")}
              />
            </div>
            <Select value={protocol} onChange={(event) => { setProtocol(event.target.value); setPage(1); }} className="h-9 w-[132px] text-xs" aria-label={t("configurations.filter.protocol")}>
              <option value="">{t("common.protocol")}: {t("common.all")}</option>
              {(facets.data?.protocols ?? []).map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </Select>
            <Select value={connectivity} onChange={(event) => { setConnectivity(event.target.value); setPage(1); }} className="h-9 w-[150px] text-xs" aria-label={t("configurations.filter.connectivity")}>
              <option value="">{t("configurations.filter.connectivity")}: {t("common.all")}</option>
              {(facets.data?.connectivity ?? []).map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </Select>
            <Select value={sourceId} onChange={(event) => { setSourceId(event.target.value); setPage(1); }} className="h-9 w-[150px] text-xs" aria-label={t("configurations.filter.source")}>
              <option value="">{t("common.source")}: {t("common.all")}</option>
              {(facets.data?.sources ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            <Select value={transport} onChange={(event) => { setTransport(event.target.value); setPage(1); }} className="h-9 w-[132px] text-xs" aria-label={t("configurations.filter.transport")}>
              <option value="">{t("configurations.filter.transport")}: {t("common.all")}</option>
              {(facets.data?.transports ?? []).map((item) => (
                <option key={item.value} value={item.value}>
                  {item.value} ({item.count})
                </option>
              ))}
            </Select>
            <Select value={sort} onChange={(event) => setSort(event.target.value)} className="h-9 w-[140px] text-xs" aria-label={t("common.sort")}>
              <option value="newest">Newest</option>
              <option value="latency">Latency</option>
              <option value="host">Host</option>
              <option value="protocol">Protocol</option>
              <option value="seen">Recently seen</option>
            </Select>
            <label className="flex items-center gap-2 rounded-xl border border-white/[0.07] px-2.5 py-2 text-[11px] text-chalk-400">
              <Switch checked={favorites} onCheckedChange={(checked) => { setFavorites(checked); setPage(1); }} />
              {t("configurations.col.favorite")}
            </label>
          </div>
        }
      >
        {list.isLoading ? (
          <SkeletonTable rows={8} />
        ) : list.isError ? (
          <ErrorState title={t("state.error.title")} detail={(list.error as Error)?.message} onRetry={() => list.refetch()} />
        ) : !rows.length ? (
          <EmptyState title={t("configurations.empty")} description={t("overview.empty")} />
        ) : (
          <>
            <TableWrap>
              <Table className="min-w-[980px]">
                <thead>
                  <tr>
                    <Th className="w-9">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={(event) => toggleAll(event.target.checked)}
                        aria-label="Select all"
                        className="size-3.5 accent-[#9DFF00]"
                      />
                    </Th>
                    <Th>{t("configurations.col.protocol")}</Th>
                    <Th>{t("configurations.col.endpoint")}</Th>
                    <Th>{t("configurations.col.source")}</Th>
                    <Th>{t("configurations.col.validation")}</Th>
                    <Th>{t("configurations.col.connectivity")}</Th>
                    <Th className="text-end">{t("configurations.col.latency")}</Th>
                    <Th>{t("configurations.col.tested")}</Th>
                    <Th className="text-center">{t("configurations.col.favorite")}</Th>
                    <Th className="text-end">{t("common.details")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <Tr key={row.id}>
                      <Td>
                        <input
                          type="checkbox"
                          checked={selected.includes(row.id)}
                          onChange={(event) => toggleOne(row.id, event.target.checked)}
                          aria-label={`Select ${row.host}:${row.port}`}
                          className="size-3.5 accent-[#9DFF00]"
                        />
                      </Td>
                      <Td>
                        <ProtocolTag protocol={row.protocol} />
                      </Td>
                      <Td>
                        <span className="mono block text-[12px] text-chalk-100">
                          {row.host}:{row.port}
                        </span>
                        <span className="mono mt-0.5 block text-[10px] text-chalk-500">
                          {row.transport} · {row.security}
                          {row.sni ? ` · ${row.sni}` : ""}
                        </span>
                      </Td>
                      <Td>
                        <div className="flex flex-wrap gap-1">
                          {row.sources.slice(0, 2).map((source) => (
                            <Badge key={source.id} tone="muted" className="max-w-[120px] truncate">
                              {source.name}
                            </Badge>
                          ))}
                          {row.sources.length > 2 ? <Badge tone="muted">+{row.sources.length - 2}</Badge> : null}
                          {!row.sources.length ? <span className="text-[11px] text-chalk-500">—</span> : null}
                        </div>
                      </Td>
                      <Td>
                        <Badge tone={row.validation_status === "valid" ? "success" : "danger"}>{row.validation_status}</Badge>
                      </Td>
                      <Td>
                        <ConnectivityPill status={row.connectivity_status} />
                      </Td>
                      <Td className="mono text-end text-[12px] text-chalk-200">{formatLatency(row.last_latency_ms)}</Td>
                      <Td>
                        <span className="text-[11px] text-chalk-400">
                          {row.last_tested_at ? relativeTime(row.last_tested_at, language) : t("configurations.neverTested")}
                        </span>
                      </Td>
                      <Td className="text-center">
                        <button
                          type="button"
                          aria-label={t("configurations.col.favorite")}
                          aria-pressed={row.is_favorite}
                          disabled={!isAdmin}
                          onClick={() => bulkFavorite.mutate({ ids: [row.id], favorite: !row.is_favorite })}
                          className={cn("rounded-lg p-1.5 transition-colors", row.is_favorite ? "text-neon" : "text-chalk-500 hover:text-chalk-300")}
                        >
                          <Star className={cn("size-4", row.is_favorite && "fill-current")} />
                        </button>
                      </Td>
                      <Td className="text-end">
                        <Button variant="ghost" size="icon" onClick={() => setDetailId(row.id)} aria-label={t("common.details")}>
                          <Eye />
                        </Button>
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
            <Pagination page={list.data?.page ?? 1} pages={list.data?.pages ?? 1} total={list.data?.total ?? 0} onPage={setPage} label={t("common.total")} />
          </>
        )}
      </Section>

      <Dialog open={detailId !== null} onOpenChange={(open) => (!open ? setDetailId(null) : null)}>
        <DialogContent side="right">
          {detail.isLoading ? (
            <div className="space-y-3">
              <div className="skeleton h-6 w-56" />
              <div className="skeleton h-24 w-full" />
              <div className="skeleton h-40 w-full" />
            </div>
          ) : detail.data ? (
            <div className="space-y-5">
              <DialogHeader>
                <DialogTitle>
                  <span className="mono text-base">
                    {detail.data.host}:{detail.data.port}
                  </span>
                </DialogTitle>
                <DialogDescription>
                  {detail.data.protocol} · {detail.data.transport} · {detail.data.security} ·{" "}
                  {detail.data.sni ?? "no SNI"}
                </DialogDescription>
              </DialogHeader>

              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{detail.data.validation_status}</Badge>
                <ConnectivityPill status={detail.data.connectivity_status} />
                {detail.data.is_favorite ? <Badge tone="neon">favorite</Badge> : null}
                {detail.data.test_agent ? <Badge tone="muted">agent: {detail.data.test_agent}</Badge> : null}
              </div>

              <div className="grid grid-cols-2 gap-2">
                {[
                  { label: t("configurations.detail.fingerprint"), value: detail.data.fingerprint },
                  { label: t("configurations.col.latency"), value: formatLatency(detail.data.last_latency_ms) },
                  { label: "avg latency", value: formatLatency(detail.data.latency_avg_ms) },
                  { label: "failures", value: String(detail.data.failure_count) },
                  { label: "first seen", value: formatDateTime(detail.data.first_seen_at, language) },
                  { label: "last seen", value: formatDateTime(detail.data.last_seen_at, language) },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                    <p className="text-[9px] uppercase tracking-wider text-chalk-500">{item.label}</p>
                    <p className="mono mt-0.5 break-all text-[11px] text-chalk-100">{item.value}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                <p className="text-[9px] uppercase tracking-wider text-chalk-500">{t("configurations.detail.canonical")}</p>
                <p className="mono mt-1 break-all text-[10px] text-chalk-400">{detail.data.canonical_endpoint}</p>
              </div>

              <div>
                <p className="mb-2 text-xs font-medium text-chalk-200">{t("configurations.detail.latency")}</p>
                {detail.data.latency_samples.length ? (
                  <div className="flex h-16 items-end gap-1 rounded-xl border border-white/[0.05] bg-ink-950/40 p-2">
                    {detail.data.latency_samples.map((value, index) => {
                      const max = Math.max(...detail.data.latency_samples);
                      return (
                        <div
                          key={index}
                          className="flex-1 rounded-sm bg-violet/70"
                          style={{ height: `${Math.max(6, (value / max) * 100)}%` }}
                          title={formatLatency(value)}
                        />
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-chalk-500">{t("configurations.detail.noSamples")}</p>
                )}
              </div>

              <div>
                <p className="mb-2 text-xs font-medium text-chalk-200">{t("configurations.detail.provenance")}</p>
                <div className="space-y-1.5">
                  {detail.data.source_links.map((source) => (
                    <div key={source.source_id} className="flex items-center justify-between gap-2 rounded-xl border border-white/[0.05] bg-ink-950/40 px-3 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-[11px] text-chalk-200">{source.name}</p>
                        <p className="mono text-[10px] text-chalk-500">
                          {source.occurrences} occurrences · first {relativeTime(source.first_seen_at, language)}
                        </p>
                      </div>
                      <span className="mono shrink-0 text-[10px] text-chalk-500">{source.slug}</span>
                    </div>
                  ))}
                  {!detail.data.source_links.length ? <p className="text-xs text-chalk-500">{t("common.noData")}</p> : null}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="config-note">{t("configurations.detail.notes")}</Label>
                <Textarea
                  id="config-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder={t("configurations.detail.notesPlaceholder")}
                  maxLength={1000}
                  disabled={!isAdmin}
                />
                <div className="flex items-center justify-between gap-2">
                  <label className="flex items-center gap-2 text-[11px] text-chalk-400">
                    <Switch
                      checked={detail.data.is_favorite}
                      disabled={!isAdmin}
                      onCheckedChange={(checked) => saveNote.mutate({ is_favorite: checked })}
                    />
                    {t("configurations.col.favorite")}
                  </label>
                  <Button variant="primary" size="sm" onClick={() => saveNote.mutate({ notes: note })} disabled={!isAdmin || saveNote.isPending}>
                    {t("configurations.detail.save")}
                  </Button>
                </div>
              </div>

              <InfoNote tone="info">{t("configurations.detail.credentials")}</InfoNote>
            </div>
          ) : (
            <ErrorState title={t("state.error.title")} detail={(detail.error as Error)?.message} onRetry={() => detail.refetch()} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
