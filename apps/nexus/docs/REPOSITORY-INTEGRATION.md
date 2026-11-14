# Repository integration

The user requested consolidating the app with the hourly bank. The application now lives under
`apps/nexus/` in `Adan03ac/ADAN-V2Ray-Free-Pack`. This supersedes the historical dedicated-repo
choice. The previous audit remains a record of the original stabilization delivery.

## Boundaries

Root `build.py`, `sources.txt`, `subscription.txt`, `subscription_base64.txt`, `status.json` and
`.github/workflows/hourly-update.yml` are preserved. The hourly workflow keeps its cron
`7 * * * *` and `contents: write`. The separate `nexus-ci.yml` has `contents: read` and path filters,
so hourly bank-only commits do not trigger application CI. App publication stays under its own
`data/published/` directory or Docker appdata volume.

`INGESTION_UPSTREAM_ONLY=true` selects only the `adan-public-bank` source for scheduled/all-source
refreshes. Explicit admin refresh of another configured source still works. The application polls
the public bank once per configured interval; it does not receive a webhook from Actions. The
GitHub refresh and local polling are separate clocks. Reduce `INGESTION_INTERVAL_MINUTES` if
faster propagation is needed. A configured cron alone does not prove scheduled executions; check
Actions history. GitHub schedules may be delayed or skipped.

## Local test

With Python 3.12+ and Node.js 22+, from the repository root:

```bash
python apps/nexus/scripts/run_local.py
```

On Windows, `py -3.12 apps/nexus/scripts/run_local.py` also works. Choose a local admin email and
password when prompted; the password is not echoed. The script installs dependencies in a venv,
runs `npm ci`, applies SQLite migrations, imports the checked-out root bank using the ordinary
validation/dedup/encryption pipeline, then starts API and Next dev servers bound to loopback.
Visit http://localhost:3000. Keep the terminal running; Ctrl+C stops both processes.

The script refuses an existing app/backend `.env` to avoid silently targeting a previously
configured environment. Use the manual or Docker instructions for an existing setup. Its local
configuration/key is stored in `apps/nexus/data/local-runtime.json`, outside version control.
Keep it private and back it up with the DB. It is created with mode 0600 on POSIX; on Windows
protect the working folder with suitable ACLs. No actual credentials are included in this repo.

The initial bank is a checkout snapshot, not a live availability guarantee. To refresh it while
offline from the application, stop the launcher, run `git pull`, then restart. After startup the
worker normally reads updated bank output from GitHub. Package installation and remote refreshes
need network access. There is no browser PWA/offline service worker.

## Explicit snapshot import

After migrations, from `apps/nexus/backend/`:

```bash
python -m scripts.import_repository_bank --bank ../../../subscription.txt
```

The import reads a bounded local file, never probes endpoints or modifies root bank files, and
prints only counts and a SHA256. Unchanged normalized configurations are deduplicated. A link
accepted by the older root scheme-prefix collector may be excluded by the app's stricter syntax
parser, so the two counts can differ. Imported rows begin as `untested`; this is not VPN testing.

For Docker, after starting the private stack:

```bash
cd apps/nexus
container_id=$(docker compose ps -q backend)
docker cp ../../subscription.txt "$container_id:/tmp/repository-bank.txt"
docker compose exec -T backend python -m scripts.import_repository_bank --bank /tmp/repository-bank.txt
```

## CI and hosting

`Nexus verification` runs backend regressions/SQLite migration checks, frontend typecheck/build/
npm audit, and a disposable Docker stack with PostgreSQL, Redis, backend, worker and frontend.
The stack job uses generated test credentials, imports the checked-out bank, and verifies login,
session cookies, real imported counts, subscription generation/revocation and logout over the
Next.js proxy. All HTTP tests use loopback; VPN endpoints are not probed.

GitHub Actions does not host the application. A running local computer or persistent server is
required. No public deployment is configured by this merge. Remaining release gates from the
audit still apply; passing CI does not establish a working VPN connection or complete production
readiness. See `DEPLOYMENT.md` for Docker, HTTPS, backup and recovery instructions.
