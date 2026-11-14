# API reference (v1)

Base URL: `/api/v1` · OpenAPI UI: `/api/docs` · Schema: `/api/openapi.json`

## Authentication

Session cookie (`nexus_session`, HttpOnly) plus CSRF cookie (`nexus_csrf`, readable).

```bash
# login
curl -s -c jar.txt -H 'Content-Type: application/json' \
  -d '{"email":"admin@adan.local","password":"…"}' \
  http://localhost:8000/api/v1/auth/login

# authenticated read
curl -s -b jar.txt http://localhost:8000/api/v1/dashboard/summary

# mutation: CSRF header must match the cookie
CSRF=$(grep nexus_csrf jar.txt | awk '{print $7}')
curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" -X POST \
  http://localhost:8000/api/v1/automation/refresh
```

Roles: `admin` (all operations) and `read_only` (GET only). Every mutating endpoint also verifies
the request `Origin` when a browser sends one.

| Status | Meaning |
| --- | --- |
| 401 | No/expired session |
| 403 | Wrong role, CSRF mismatch, or foreign origin |
| 409 | Duplicate source slug, pipeline already running, disabled source |
| 422 | Validation failure (URL rejected by SSRF policy, unknown protocol filter…) |
| 423 | Account locked after repeated login failures |
| 429 | Rate limited (`Retry-After` provided) |
| 501 | Cloudflare deployment intentionally unimplemented |

## Endpoints

### Authentication

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | Creates a session, returns user + CSRF token |
| POST | `/auth/register` | public | Self-service signup; always creates a `read_only` account and starts a session (disable with `ALLOW_REGISTRATION=false`) |
| GET | `/auth/me` | session | Current user, CSRF token, expiry |
| POST | `/auth/logout` | session | Revokes the session and clears cookies |
| GET | `/auth/users` | admin | Operator list |
| POST | `/auth/users` | admin + CSRF | Creates an operator |
| PATCH | `/auth/users/{id}` | admin + CSRF | Changes role or activation; self-demotion/deactivation returns `409` |

### Dashboard & analytics

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/dashboard/summary?days=7\|30\|90` | session | KPIs, growth, protocol/source contribution, health, latency, heatmap, runs, upstream |
| GET | `/analytics/overview` | session | Aggregates + source reliability |
| GET | `/analytics/series?days=` | session | Growth, latency, pipeline activity, heatmap |

### Sources

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/sources?search=&source_type=&status=&page=&page_size=` | session | Paginated registry |
| GET | `/sources/{id}` | session | Detail + fetch history + contribution |
| POST | `/sources` | admin + CSRF | Create (SSRF-validated URL) |
| PATCH | `/sources/{id}` | admin + CSRF | Edit / enable / disable |
| POST | `/sources/{id}/refresh` | admin + CSRF | Queue a single-source run (202) |

### Configurations

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/configurations?search=&protocol=&source_id=&connectivity=&transport=&favorites=&sort=&page=` | session | Paginated list (no credentials) |
| GET | `/configurations/facets` | session | Filter counts |
| GET | `/configurations/{id}` | session | Detail, latency samples, provenance, canonical endpoint |
| PATCH | `/configurations/{id}` | admin + CSRF | Favorite, tags, notes |
| POST | `/configurations/bulk-favorite` | admin + CSRF | Bulk favorite toggle (≤200 ids) |

### Health

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| POST | `/health-tests` | admin + CSRF | Queue a job (`limit ≤ 50`, stages subset of syntax/dns/tcp) |
| GET | `/health-tests?job_id=&configuration_id=&status=` | session | Recent results |
| GET | `/health-tests/jobs` | session | Jobs + queue snapshot |
| GET | `/health-tests/summary` | session | Agent info, states, unavailable stages |

### Subscription Studio

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/subscription-profiles` | session | Profiles visible to the caller |
| POST | `/subscription-profiles` | admin + CSRF | Create profile |
| PATCH | `/subscription-profiles/{id}` | admin + CSRF | Update filters |
| DELETE | `/subscription-profiles/{id}` | admin + CSRF | Delete profile + tokens |
| GET | `/subscription-profiles/{id}/preview` | session | Matching preview + library size |
| POST | `/subscription-profiles/{id}/render` | admin + CSRF | Issue token, persist generation time, return URL |
| GET | `/subscription-profiles/{id}/export` | session | File download (plain/Base64/JSON) |
| POST | `/subscription-profiles/{id}/tokens` | admin + CSRF | Additional token |
| POST | `/subscription-profiles/tokens/{tokenId}/revoke` | admin + CSRF | Revoke |

### Public (no session)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/public/subscriptions/{token}?format=plain\|base64\|json` | Renders the profile; `Cache-Control: no-store`; 404 for unknown/revoked/expired |

Tokens are random 32-byte URL-safe strings; only their SHA-256 hash is stored.

### Automation & system

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/automation/runs?limit=` | session | Run history + scheduler + error sources |
| GET | `/automation/runs/{id}` | session | Single run detail |
| POST | `/automation/refresh` | admin + CSRF | Queue full ingestion (202 / 409) |
| GET | `/automation/schedule` | session | Scheduler status, upstream snapshot, workflow runs, safeguards |
| GET | `/system/health` | public | Liveness/readiness of this process |
| GET | `/system/settings` | session | Stored preferences, runtime values, capabilities |
| PATCH | `/system/settings` | admin + CSRF | Update a settings namespace |
| GET | `/system/publication` | session | Manifest, files, sizes, mode |
| GET | `/system/audit-logs?limit=` | admin | Audit trail |

### Cloudflare

| Method | Path | Role | Description |
| --- | --- | --- | --- |
| GET | `/cloudflare/status` | session | Configured flags, capability matrix, considerations, empty deployment list |
| POST | `/cloudflare/deployments` | admin + CSRF | Always `501`; records an audit entry with outcome `rejected` |

## Error shape

```json
{ "detail": "Human-readable reason" }
```

Validation errors from FastAPI use the standard `detail: [{loc, msg, type}]` array.

## Rate limits

| Bucket | Limit |
| --- | --- |
| login | `LOGIN_RATE_LIMIT` per IP per minute (default 10) |
| registration | `REGISTER_RATE_LIMIT` per IP per hour (default 5) |
| source writes | 30–60/min |
| source refresh | 6/min |
| health job start | 6/min |
| subscription render | 20/min |
| automation refresh | 4/min |
