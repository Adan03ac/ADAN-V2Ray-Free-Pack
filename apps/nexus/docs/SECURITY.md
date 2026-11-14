> Current findings, fixes, remaining risks and evidence: [AUDIT-fa.md](AUDIT-fa.md). Deployment guidance: [DEPLOYMENT.md](DEPLOYMENT.md). The original security overview below predates stabilization.

# Security notes

## Threat model

| Asset | Threat | Control |
| --- | --- | --- |
| Operator accounts | Credential stuffing, brute force | bcrypt (cost 12), per-IP rate limit, 5-failure lockout for 15 min, generic error text |
| Sessions | Fixation, theft, replay | Random 32-byte tokens stored as SHA-256, HttpOnly + SameSite=Lax, 12 h expiry, revocation on logout |
| Mutations | CSRF | Double-submit header/cookie + server-side session match + `Origin` allow-list check |
| Share-link secrets | Leakage via API or backups | Fernet encryption at rest (key derived from `SECRET_KEY`), never serialized; listings expose only a masked hint |
| Source fetching | SSRF into internal networks | HTTPS-only, credentials-in-URL rejected, DNS resolution of every host, denial of private/loopback/link-local/reserved/multicast, redirect re-validation (max 3), 8 MiB cap |
| Public subscription tokens | Enumeration | 32-byte URL-safe tokens, hashed at rest, revocable, `no-store` responses |
| Abuse of testing | Port scanning | Only registered configurations, batch cap 50, concurrency cap 16, timeouts, no arbitrary host input |
| Privilege escalation | Read-only → admin | Role checked server-side on every mutation (`require_csrf` implies admin) |
| Log leakage | Secrets in logs | Structured logger redacts password/token/cookie/uuid keys and truncates long strings |

## Implemented controls

- **Input validation** — Pydantic models, bounded strings/lists, protocol/source-type enums,
  numeric ranges, tag sanitisation, slug regex.
- **SQL safety** — SQLAlchemy Core/ORM with bound parameters; no string-built SQL.
- **CORS** — explicit origin list, credentials allowed only for those origins.
- **Security headers** — `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  restrictive `Permissions-Policy` and a `default-src 'none'` CSP on API responses.
- **Secret handling** — `.env` is git-ignored; `.env.example` contains placeholders only; no
  credential is hardcoded; Cloudflare tokens, if ever added, must live in server environment.
- **Audit trail** — login success/failure/blocked, source and profile mutations, refreshes,
  settings changes, token revocation, rejected deployments.
- **Database exposure** — PostgreSQL/Redis are not published in `docker-compose.yml`.
- **Untrusted processes** — health tests use sockets only; no shell execution anywhere in the
  request path, and no user-supplied command is ever run.

## Explicit non-goals / gaps

- No MFA/WebAuthn, no password reset or change endpoint (rotate the bootstrap secret and recreate).
- CSRF relies on double-submit plus strict `SameSite=Lax`; a subdomain attacker would need to
  control cookies, which the deployment guidance forbids.
- No per-account (only per-IP) login throttling; add a shared Redis limiter for multi-node setups.
- The SQLite development path lacks Postgres row-level isolation; do not run SQLite in production.
- No dependency scanner is wired into CI in this delivery; run `pip-audit` and `npm audit` in the
  pipeline before exposure.
- Public subscriptions are served over whatever scheme the deployment terminates; enforce HTTPS
  at the reverse proxy and set `COOKIE_SECURE=true`.

## Deployment checklist

1. `SECRET_KEY` = 48+ random bytes, unique per environment.
2. `BOOTSTRAP_ADMIN_PASSWORD` strong, then rotate it out of the environment after first boot.
3. `ENVIRONMENT=production`, `COOKIE_SECURE=true`, TLS terminated in front of the frontend.
4. `ALLOWED_ORIGINS` limited to the real UI origin(s).
5. `ALLOW_PRIVATE_SOURCE_HOSTS=false` (default) unless you intentionally ingest an internal feed.
6. Postgres and Redis reachable only on the private network.
7. Back up the `appdata` volume and PostgreSQL nightly; test a restore.
8. Set `GITHUB_TOKEN` only if workflow history is required (read-only scope).
9. Leave `CLOUDFLARE_ENABLED=false` until the deployment module is implemented and reviewed.

## Cloudflare, terms and licensing

Deployments are **not implemented**. Before enabling anything:

- Review Cloudflare Workers/Pages free-tier quotas (requests/day, build minutes, CPU ms). They are
  finite; no "unlimited bandwidth" claim is made anywhere in this project.
- Review Cloudflare's Terms of Service regarding proxy/VPN configuration distribution.
- Treat BPB Worker Panel, BPB Wizard and Nova Proxy as third-party licensed projects. None of their
  code is copied here. Any future integration must first verify the license and attribution duties.
- Store a scoped token (Workers Scripts:Edit, Account Settings:Read) server-side only; never inject
  it into the browser bundle or commit it.
