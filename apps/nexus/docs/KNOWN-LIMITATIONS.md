> Current detailed limitations and release blockers: [AUDIT-fa.md](AUDIT-fa.md).

# Known limitations

Written against the delivered build. Anything listed here is **not** implemented, **not**
verified, or deliberately refused.

## Capability gaps

1. **No end-to-end tunnel verification.** The health engine performs syntax validation, DNS
   resolution and TCP connect. It never performs a VLESS/VMess/Trojan/SS/Hysteria2 handshake, so
   `verified_working_configurations` is `0` with `verification_available: false`.
2. **No protocol-level testing** (TLS handshake, WebSocket upgrade, gRPC, QUIC). Needs an isolated
   Xray/sing-box process with resource limits; not built.
3. **No Iran-based testing agent.** Measurements carry `agent_region` exactly as configured
   ("unspecified (no geo verification)"). No claim of Iranian vantage point is made.
4. **No country inference or country filters.** The Studio explains this instead of faking it.
5. **Cloudflare deployments unimplemented.** Read-only status, capability matrix, limits and
   licensing notes exist; `POST /cloudflare/deployments` returns `501`.
6. **No GitHub push publication.** `PUBLISH_MODE=github` returns a clear "not implemented"
   result; the local mirror in `data/published` is used instead. The existing Actions workflow
   remains authoritative.
7. **No GitHub workflow control.** Run history requires `GITHUB_TOKEN`; dispatching the workflow
   is not implemented.
8. **No password change / reset / MFA.** Account management is limited to create + list + role.
9. **No PWA service worker.** Offline behaviour is limited to clear indicators and retained
   server data; a cached dashboard cannot refresh subscriptions or establish VPN connections.
10. **No multi-user profile isolation beyond roles.** Read-only users see all telemetry; profile
    ownership exists in the schema but admins can see every profile.
11. **No Clash/sing-box client formats.** Only plain, Base64 and JSON are implemented and tested.
12. **No alert delivery** (email/webhook). Errors are surfaced in-app only.
13. **No backup/restore UI.** Use `pg_dump` and the `appdata` volume.

## Verification gaps in this delivery

- **Docker was not executed.** The sandbox denies access to the Docker socket. `docker compose
  config` validates interpolation and structure, but no container was built or started here.
  Postgres/Redis paths are therefore unproven at runtime; SQLite was used for all live checks.
- **Frontend was not visually inspected.** `tsc --noEmit`, `next build` and HTTP checks passed;
  no browser was opened, so pixel-level fidelity to the reference is unverified.
- **No browser/end-to-end interaction tests.** Backend behaviour is covered by 55 pytest tests;
  UI flows are exercised only through type checking, build and server responses.
- **Health tests were run with syntax+DNS only**, to avoid probing arbitrary third-party hosts at
  scale from the delivery VM. TCP code paths are unit-shaped but not measured here.
- **Upstream availability varies.** `dashboard/summary` and `automation/schedule` show
  "unavailable" rather than inventing values when GitHub cannot be reached.

## Design limits

- Deduplication groups by canonical endpoint + credential digest. Two genuinely distinct nodes
  that share host/port/transport/SNI/credential are treated as one record.
- `max_configs` caps exports at 500; Library-wide counting above that is approximate only in the
  Studio's "matched" hint.
- The heatmap uses UTC dates.
- Scheduler jitter is process-local; a multi-replica deployment must keep exactly one worker.
- Retention runs after ingestion only; a system that never ingests never prunes.

## Data honesty guarantees

- No metric is estimated, interpolated or seeded. Empty states are rendered instead.
- No sample configurations are inserted into production tables. Test fixtures stay in tests.
- Failed publications never delete the previous bank.
- The footer and Cloudflare page state the limits of what the platform can promise.
