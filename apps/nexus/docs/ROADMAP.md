> Updated priorities and release gates: [AUDIT-fa.md](AUDIT-fa.md). The original roadmap below is historical and does not override verified delivery status.

# Development roadmap

## Phase 1 — Functional MVP · **delivered**

- Real dashboard backed exclusively by database aggregates
- Existing GitHub source integration (three direct feeds + the published ADAN bank as a mirror)
- Source registry with adapter interface, conditional HTTP and per-fetch diagnostics
- Configuration explorer with filters, facets, favorites, provenance and credential-free payloads
- Basic subscription builder: filters, preview, plain/Base64/JSON, revocable tokens, QR
- Hourly update visibility: local scheduler, run history, upstream `status.json` snapshot
- Session authentication, admin/read-only RBAC, CSRF, audit log
- Responsive UI, English/Persian with RTL, honest empty/error states

## Phase 2 — Intelligence · **partially delivered**

Delivered: syntax/DNS/TCP health engine with bounded concurrency, latency history per
configuration, source reliability analytics, advanced filtering (protocol, source, transport,
connectivity, favorites, search), in-app error surfacing.

Remaining:

- Protocol-level verification in an isolated Xray/sing-box sandbox (per-protocol adapters)
- Distributed testing agents with declared locations, including an authorized Iran agent
- Alert delivery (email/webhook) and alert rules
- Latency percentile charts and time-window comparisons
- Source auto-quarantine after repeated failures

## Phase 3 — Personal infrastructure · **architecture only**

Prepared: provider protocol (`PublicationProvider`), `deployments` table, Cloudflare capability
matrix, scoped-token configuration, audit hooks, explicit `501`.

Remaining:

- Cloudflare API client with scoped tokens, Workers/Pages deploy, version history, rollback
- Secret management per environment, deployment log redaction
- BPB compatibility review (license first), independent implementation where required
- Multi-user management beyond roles, per-user quotas
- Deployment monitoring with real quota consumption from the provider

## Phase 4 — Advanced platform · **planned**

- Distributed test agents and geo-verified measurements
- Additional subscription formats via tested adapters (Clash, sing-box)
- Backup/restore tooling, export of the whole bank + telemetry
- PWA shell with cached read-only dashboard and explicit offline banners
- Retention policies per data class with operator UI
- Horizontal scaling guidance: shared Redis limiter, dedicated worker deployment

## Engineering follow-ups

1. CI pipeline: `pytest`, `ruff`, `tsc`, `next build`, `pip-audit`, `npm audit`.
2. Postgres integration tests (currently SQLite) and a migration-downgrade test.
3. Playwright smoke tests for login, filters and Studio generation.
4. Replace the file lock with an advisory Postgres lock when running multiple API replicas.
5. Move health execution to a queue (Redis/RQ or DB-backed) with per-job cancellation.
