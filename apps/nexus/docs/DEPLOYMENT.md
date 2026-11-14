# Deployment and recovery — stabilization build

This build is locally tested. Docker/PostgreSQL/Redis integration is not yet executed. Follow `AUDIT-fa.md` for release gates. Do not treat these instructions as evidence that a public deployment was tested.

## Local Docker setup

Prerequisites: Docker Engine with Compose v2, enough resources for PostgreSQL, Redis, API, worker and Next.js, and package/image registry access during build.

```bash
cp .env.example .env
# Edit .env privately. Never commit it or paste its contents into logs.
# Set unique SECRET_KEY (at least 32 characters), BOOTSTRAP_ADMIN_PASSWORD
# (10-72 UTF-8 bytes), and POSTGRES_PASSWORD.
# Use a URL-safe random PostgreSQL password because Compose embeds it in a URL.
# Set PUBLIC_BASE_URL=http://localhost:3000 and ALLOWED_ORIGINS=http://localhost:3000.
# Local offline operation: INGESTION_ENABLED=false and UPSTREAM_ENABLED=false.
docker compose config --quiet
docker compose build
docker compose up -d
```

Open `http://localhost:3000`. The frontend binds loopback by default. PostgreSQL, Redis and backend have no host-published ports. The Docker bridge is **not** an egress sandbox.

Only the backend entrypoint runs Alembic. The worker waits for backend health before starting. Leave `DATABASE_AUTO_CREATE=false` in production. Use one API process until health jobs move to a persistent shared queue. Keep the original `SECRET_KEY` across restart/upgrade/restore; changing it makes stored Fernet links unreadable. Existing users are not overwritten by bootstrap variables.

Do not set `ALLOW_PRIVATE_SOURCE_HOSTS=true` in a normal production deployment. TCP health is disabled by default. To authorize a specific target you own or have permission to test, set `HEALTH_ALLOW_TCP=true` and a narrow, public `HEALTH_AUTHORIZED_CIDRS` list; private/non-global addresses remain blocked. An empty list permits no TCP probes. QUIC/UDP tunnel verification is unavailable.

Check startup privately with `docker compose ps` and `docker compose logs --tail=100 backend worker`. Do not share raw logs until they are checked for secrets. Only credential-free health status and test summaries should leave the host.

## Public deployment gate

Do not publish this stack before completing the P1 gates in the audit. Public deployment needs separate authorization. Prepare a reverse proxy with HTTPS; set `PUBLIC_BASE_URL` and an exact `ALLOWED_ORIGINS`, `COOKIE_SECURE=true`, `ALLOW_REGISTRATION=false` and empty `ALLOWED_ORIGIN_SUFFIXES`. Do not use wildcard origins.

Publish only the intended TLS frontend. Any change from loopback `FRONTEND_BIND` is an operator decision. Protect Redis and internal service access, and restrict egress independently. Disable/redact full subscription paths in reverse-proxy access logs: URLs contain bearer tokens. Uvicorn should trust forwarded headers only from exact proxy addresses you control. Never trust arbitrary forwarded headers. `API_PROXY_TARGET` must be set at **build time** for Next rewrites; changing only a runtime env var is not a reliable way to change an already-built rewrite destination.

Readiness reporting still needs stronger dependency probes. Do not rely on HTTP 200 alone as evidence that Redis, scheduler or publication are healthy.

## SQLite development without Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
# Set persistent SECRET_KEY, bootstrap password, local writable DATABASE_URL,
# PUBLISH_DIR and PIPELINE_LOCK_PATH. Set REDIS_URL to empty for local memory.
# API_PROXY_TARGET=http://127.0.0.1:8000
# PUBLIC_BASE_URL=http://localhost:3000
# INGESTION_ENABLED=false; EMBEDDED_WORKER=false; UPSTREAM_ENABLED=false
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, install frontend dependencies and run `npm run dev` from `frontend/`. Dependencies must be installed before disconnected use. Manual sources and stored data work locally; fetching a new remote feed requires network access. There is no offline browser service worker in this build.

## SQLite backup and restore

Prefer stopping application writes and the worker while making a coordinated backup of database, publications and the encryption key. The database utility uses SQLite's backup API and works with WAL; it validates source and destination integrity and creates a **new** destination with mode 0600 on POSIX.

From `backend/`, replace the example paths with paths on your own host:

```bash
../.venv/bin/python -m scripts.sqlite_backup backup /srv/nexus/data/nexus.db /srv/backups/nexus-20261114.db
../.venv/bin/python -m scripts.sqlite_backup restore /srv/backups/nexus-20261114.db /srv/nexus-restored/nexus.db
```

The destination parent must already exist. Existing files, including symlinks, are refused. Restoring does not replace the active DB: start a separate isolated instance against the restored path, using the **same** original `SECRET_KEY`, verify records and exports, and only then explicitly plan a cutover. The utility validates SQLite structure; it does not validate that a chosen key decrypts every application record.

Store the original secret key and `.env` separately in a protected secret store. Backups contain sensitive metadata; legacy manual URLs may be plaintext. Publication files contain share-link credentials by design. Restrict access and encrypt off-host backups. Do not include `.env`, DBs, publication output or tokens in a source ZIP.

## PostgreSQL backup drill (instructions only; untested here)

On an authorized private deployment, stop writers before a coordinated DB/publication backup:

```bash
mkdir -p backups
chmod 700 backups
umask 077
docker compose stop backend worker
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/nexus.dump
```

Keep the same environment secret key separately and archive the publication volume using your host's protected backup tooling. Restore first into a **new test database**, never over the live database. For a test DB named `nexus_restore_test` that does not already exist:

```bash
docker compose exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" nexus_restore_test'
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d nexus_restore_test --no-owner --exit-on-error' < backups/nexus.dump
docker compose start backend worker
```

Inspect the test database, run an isolated app against it, verify decryption/subscription rendering, and record a successful recovery before any live cutover. These commands deliberately do not drop databases or delete volumes. Database cutover, public deployment and real-credential operations require explicit authorization.

## Rollback

The delivered ZIP contains the unmodified original archive at `rollback/original-source.zip` and a source diff at `rollback/stabilization.patch`. Extract the original into a separate directory for comparison. Do not run two schedulers against one DB. No database schema migration was introduced by this stabilization; original IDs and ciphertext format remain. New manual source values use `nexus:fernet:` in the existing URL column and need the updated adapter; exports show `<redacted>` in the API. Before reverting code that predates this encoding, use the pre-upgrade DB backup or plan conversion on a copy. Strict UUID validation affects newly ingested VLESS/VMess links, not stored rows. Old plaintext manual sources continue to import.

Do not restore old application files over live data. Never use `docker compose down -v` as a routine rollback: it destroys volumes.
