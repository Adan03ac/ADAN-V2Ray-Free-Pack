> Current decision: user-requested consolidation under `apps/nexus/` in the hourly bank repository. See [REPOSITORY-INTEGRATION.md](REPOSITORY-INTEGRATION.md). The earlier decision below is historical.

# Repository strategy (Part 31 decision)

## What exists today

`Adan03ac/ADAN-V2Ray-Free-Pack` contains exactly:

```
.github/workflows/hourly-update.yml   # cron '7 * * * *' + manual dispatch, commits artifacts
build.py                             # fetch → parse → dedupe → write bank (stdlib only)
sources.txt                          # 3 direct feeds + 2 commented discovery pages
status.json                          # last run: timestamp, total, per-source results
subscription.txt                     # 10,988 raw links (2.7 MB)
subscription_base64.txt              # same bank, Base64 (3.7 MB)
README.md
```

The workflow fetches each source, parses share links by scheme prefix, dedupes on the raw string,
and commits only when `git diff --cached` is non-empty. This pipeline is small, dependency-free
and entirely independent of any server — the property most worth protecting.

## Options

### A. Extend the existing repository with `frontend/`, `backend/`, `infra/`

**Pros** — one clone; the app is adjacent to the artifacts it reads.

**Cons**
- ~11k-file churn every hour in the same repository as the application; every workflow commit
  triggers app CI, and every app merge risks touching the bank.
- Secrets, deployment configuration and a growing Python/Node tree share a repository whose
  Actions token needs `contents: write`.
- A scheduled commit that conflicts with a release branch is a real operational hazard.
- Large binary-ish artifacts (2.7 MB and 3.7 MB, rewritten hourly) bloat every clone of the app.

### B. Keep the public engine separate; build the application in its own repository

**Pros**
- The public bank keeps exactly the failure surface it has today; `build.py` and the cron never
  depend on the database, the API or Docker.
- App CI is not triggered by hourly data commits; releases are not raced by the scheduler.
- Least-privilege: the app repository needs no `contents: write` on the public bank.
- The app can be deployed, rebuilt or taken offline without affecting subscription URLs.
- The application can later be hosted in Iran while the public mirror stays on GitHub.

**Cons** — two repositories to maintain; requires documenting how the app consumes the bank.

## Decision: **Option B**

This worktree is the dedicated application repository. The public repository is untouched: its
files, URLs and hourly workflow remain byte-for-byte authoritative.

### What the application reads from the public bank (read-only)

| Artifact | Use |
| --- | --- |
| `status.json` | Upstream "public bank workflow" card, last publish time, per-source status |
| `subscription.txt` | Registered as the `adan-public-bank` mirror source, giving the dashboard full coverage of the published bank |

No write path to GitHub exists. `PUBLISH_MODE=github` returns an explicit "not implemented"
result; `PUBLISH_MODE=local` writes an atomic mirror under `data/published/`.

### Proposed changes if the two are ever combined

Do not copy files into the public repository without review. If consolidation is later required:

1. Create `apps/nexus/` and move the application wholesale; keep `build.py`, `sources.txt` and the
   three generated artifacts at the repository root, unchanged.
2. Add `.github/workflows/nexus-ci.yml` scoped to `apps/nexus/**` so hourly bank commits do not
   trigger application pipelines.
3. Split permissions: the hourly workflow keeps `contents: write`; the application workflows get
   `contents: read`.
4. Never let the application write `subscription.txt`, `subscription_base64.txt` or `status.json`.
   The local mirror stays under `apps/nexus/data/published/`.
5. Document the move in the public README and verify the two raw URLs still resolve after the
   change.

### Preserved public URLs

```
https://raw.githubusercontent.com/Adan03ac/ADAN-V2Ray-Free-Pack/main/subscription_base64.txt
https://raw.githubusercontent.com/Adan03ac/ADAN-V2Ray-Free-Pack/main/subscription.txt
```

These are unchanged by this delivery and must remain so. The application's own public endpoint is
separate and token-scoped:

```
GET /api/v1/public/subscriptions/{revocable-token}
```
