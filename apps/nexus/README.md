> Run `python apps/nexus/scripts/run_local.py` from the repository root for a local test. See [repository integration](docs/REPOSITORY-INTEGRATION.md). This app now lives beside the independent hourly bank publisher.

> Stabilization update (2026-11-14): start with [the verified audit](docs/AUDIT-fa.md) and [deployment/recovery instructions](docs/DEPLOYMENT.md). The historical MVP overview below is retained for context; the audit is authoritative for implementation/test status. Public production release is not yet verified. Registration and TCP probing now default to disabled; a persistent SECRET_KEY is required in every environment.

# ADAN NEXUS | CONNECT

**Connectivity Intelligence and Subscription Management Platform.**

A working, self-hostable operator console for a public proxy-subscription pipeline: source
registry, deterministic protocol parsing, provenance tracking, isolated reachability testing,
composable subscription exports and honest operational analytics.

> The public bank in [`Adan03ac/ADAN-V2Ray-Free-Pack`](https://github.com/Adan03ac/ADAN-V2Ray-Free-Pack)
> is unchanged. Its `build.py`, `sources.txt`, `status.json`, `subscription.txt`,
> `subscription_base64.txt` and hourly GitHub Actions workflow keep working with or without this
> application. This repository is a separate application (see
> [docs/REPOSITORY-STRATEGY.md](docs/REPOSITORY-STRATEGY.md)).

---

## 1. What is actually implemented

| Module | Status |
| --- | --- |
| **A. Public Source Intelligence** | **Implemented.** Registry, 5 adapter types, conditional HTTP, ETag/Last-Modified, retries, per-fetch diagnostics, provenance. |
| **B. Configuration Bank & Health Testing** | **Implemented** for syntax/DNS/TCP. Protocol-level and end-to-end tunnel verification are **not** implemented. |
| **C. Personal Subscription Studio** | **Implemented.** Filters, preview, plain/Base64/JSON export, revocable hashed tokens, QR codes. |
| **E. Analytics, Monitoring & Automation** | **Implemented.** DB-derived KPIs, growth/latency/pipeline series, heatmap, run history, scheduler, upstream snapshot. |
| **D. Cloudflare Deployment Manager** | **Interface only.** Capability matrix, limits/licensing documentation, explicit `501` on deploy attempts. Nothing is deployed. |

Reachability is reported as `reachable` (a TCP port answered). It is never labelled *connected*
or *verified working*. There is no Iran-based test agent, so no measurement claims to originate
from Iran. Countries are not inferred.

## 2. Architecture

```
                    ┌──────────────────────────────────────────────┐
  Browser ────────► │ Next.js 15 (App Router, RSC shell, client    │
                    │ console) — shadcn-style UI, Recharts,        │
                    │ TanStack Query, Zustand                      │
                    └───────────────┬──────────────────────────────┘
                                    │ same-origin /api/* rewrite (HttpOnly cookie)
                    ┌───────────────▼──────────────────────────────┐
                    │ FastAPI  ·  /api/v1  ·  OpenAPI at /api/docs │
                    │ auth · RBAC · CSRF · rate limiting · audit   │
                    ├──────────────┬───────────────┬───────────────┤
                    │ services     │ workers       │ publishers    │
                    │ parsers      │ scheduler     │ local atomic  │
                    │ adapters     │ health pool   │ github (stub) │
                    │ fetcher      │ retention     │               │
                    └──────┬───────┴───────┬───────┴───────┬───────┘
                           │               │               │
                     PostgreSQL /      Redis (opt.)    data/published
                     SQLite (dev)      cache + RL      versions + manifest
```

Detailed design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Ingestion pipeline

`FETCH → DECODE → PARSE → NORMALIZE → VALIDATE → DEDUPLICATE → STORE → PUBLISH`

- HTTPS-only, SSRF-protected fetching (DNS-resolved address checks on every redirect hop).
- Conditional requests (`If-None-Match`, `If-Modified-Since`), 8 MiB ceiling, 25 s timeout,
  exponential backoff, per-source isolation so one failure cannot abort a run.
- Duplicate identity is the **canonical endpoint + credential digest**, not the raw string:
  renaming a node keeps one record; changing UUID, port, transport, SNI or path creates another.
- Malformed links are counted and sampled (scheme + category only) — never silently dropped, and
  never echoed with their credentials.
- Publication is atomic (`tmp` + `fsync` + `os.replace`), versioned, hash-compared, and skipped
  when the output is unchanged. A failed run never deletes the last good bank.

## 3. Quickstart (SQLite, no Docker)

Requirements: Python 3.11+, Node 20+.

```bash
# 1. Environment
cp .env.example .env                                  # required: configure persistent secrets
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp ../.env.example .env                                # edit SECRET_KEY + BOOTSTRAP_ADMIN_PASSWORD
# point DATABASE_URL at a writable path for local use, e.g.
#   DATABASE_URL=sqlite:////absolute/path/to/repo/data/nexus.db
```

`backend/.env` is read automatically. Minimum required keys:

```dotenv
SECRET_KEY=<openssl rand -base64 48>
BOOTSTRAP_ADMIN_EMAIL=admin@adan.local
BOOTSTRAP_ADMIN_PASSWORD=<at least 10 characters>
DATABASE_URL=sqlite:////absolute/path/to/repo/data/nexus.db
PUBLISH_DIR=/absolute/path/to/repo/data/published
PIPELINE_LOCK_PATH=/absolute/path/to/repo/data/pipeline.lock
EMBEDDED_WORKER=true
LOG_JSON=false
```

```bash
# 2. Database (Alembic is authoritative)
.venv/bin/alembic upgrade head

# 3. Ingest the real public feeds (≈3 s, network required)
.venv/bin/python -m scripts.ingest

# 4. API
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. UI (second terminal)
cd ../frontend
npm ci
npm run dev            # http://localhost:3000  (proxies /api/* to :8000)
```

Sign in with `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` from `backend/.env`.
The first boot creates the administrator once; later boots never overwrite it.

**Accounts:** the sign-in screen offers *Create an account*, which registers a **read-only**
operator (`POST /api/v1/auth/register`, rate-limited, enable explicitly with `ALLOW_REGISTRATION=true`; disabled by default).
Administrators can create accounts, change roles and deactivate operators in
**Settings → Operators**; self-demotion is refused so the last admin cannot lock itself out.

### Docker Compose (PostgreSQL + Redis + worker)

```bash
cp .env.example .env
# set SECRET_KEY, BOOTSTRAP_ADMIN_PASSWORD, POSTGRES_PASSWORD
docker compose up -d --build
open http://localhost:3000
```

Only port 3000 is published. PostgreSQL and Redis are internal-only. The `worker` service owns
the single ingestion scheduler; the API runs with `EMBEDDED_WORKER=false`, so there is exactly
one scheduler. **Docker could not be exercised in the delivery sandbox (no daemon access); the
this delivery only statically parsed the Compose YAML; `docker compose config` and the stack must be run on the target host.**

## 4. Interfaces

- UI: `http://localhost:3000` (Overview, Source Intelligence, Configuration Explorer,
  Health Monitor, Subscription Studio, Cloudflare Manager, Automation Center, Analytics, Settings)
- OpenAPI: `http://localhost:8000/api/docs`
- Health: `GET /api/v1/system/health`
- Public subscription: `GET /api/v1/public/subscriptions/{token}` (no session; revocable token)

Full endpoint reference: [docs/API.md](docs/API.md).

## 5. Data integrity rules

- Every dashboard number is a SQL aggregate over `configurations`, `configuration_sources`,
  `source_fetches`, `health_tests`, `pipeline_runs`.
- `verified_working_configurations` is hard-coded to `0` with `verification_available: false` and
  an explanatory note, because no end-to-end verifier exists in this build.
- `average_measured_latency_ms` is `null` until a TCP test has actually recorded a latency.
- Charts render empty states, not placeholder series.
- The Cloudflare page lists zero deployments and zero usage because none exist.
- GitHub Actions history is reported unavailable unless `GITHUB_TOKEN` is configured.
- No sample/demo rows are inserted into the database. Test fixtures live in `backend/tests/` only.

## 6. Tests

```bash
cd backend
.venv/bin/python -m pytest tests -q          # current suite: see evidence/pytest.txt
cd ../frontend
npx tsc --noEmit && npm run build
```

Coverage focus: all five protocol parsers and hostile input, Base64 detection, fingerprint
identity, dedup and idempotent re-runs, partial/total source failure, unchanged-output
publication, SSRF rejection (9 vectors), authentication/lockout/CSRF/RBAC, credential-free API
payloads, subscription exports and token revocation, health-job boundaries.

**Not covered:** browser interaction tests, live TCP measurement assertions (network-dependent),
Cloudflare API calls (unimplemented), and the Docker stack (daemon unavailable here).

## 7. Security summary

See [docs/SECURITY.md](docs/SECURITY.md). Highlights: HTTPS + SSRF-hardened egress, HttpOnly
session cookies with CSRF double-submit, bcrypt password hashing, account lockout, per-IP rate
limits, admin/read-only RBAC, audit log, Fernet-encrypted share links that are never serialized
to the API, hashed subscription tokens, restricted CORS and an origin check on mutations.

## 8. Known limitations

[docs/KNOWN-LIMITATIONS.md](docs/KNOWN-LIMITATIONS.md). The short version: no end-to-end tunnel
verification, no Iran agent, no country inference, Cloudflare deployments unimplemented, GitHub
push publication unimplemented (local mirror only), no password-change UI, no PWA service worker,
and Docker Compose is unexecuted in this environment.

## 9. Roadmap

[docs/ROADMAP.md](docs/ROADMAP.md) — Phase 1 (delivered), Phase 2 (partially delivered), Phase 3
(architecture only), Phase 4 (planned).

## 10. Repository layout

```
backend/            FastAPI app, services, workers, Alembic, pytest suite
frontend/           Next.js console (App Router, Tailwind, shadcn-style primitives)
docs/               architecture, API, security, limitations, roadmap, repository strategy
docker-compose.yml  Postgres + Redis + API + worker + UI
.env.example        every supported environment variable
```

## 11. License and third-party notices

No third-party panel code (BPB Worker Panel, BPB Wizard, Nova Proxy) is copied, vendored or
redistributed. Those projects are referenced only as interface concepts; any future integration
must review their licenses first. Public proxy configurations are untrusted third-party data:
this platform does not warrant their safety, legality, availability or performance.
