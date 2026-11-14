# ADAN V2Ray Free Pack

Aggregates public proxy share links hourly using GitHub Actions. No server is hosted by this repository.

## Subscription
After the first successful workflow run, import:
https://raw.githubusercontent.com/Adan03ac/ADAN-V2Ray-Free-Pack/main/subscription_base64.txt

## Run
Python 3.10+: `python build.py`

To enable automatic refresh, open GitHub Actions and run **Hourly subscription refresh** once. Set Actions workflow permissions to **Read and write permissions** if commits fail. The scheduled cron is minute 07 of every hour, subject to GitHub delays.

Sources are in `sources.txt`. Commented URLs are discovery pages, not direct subscriptions.

**Safety:** Public nodes are untrusted. No guarantee of connectivity, privacy, unlimited bandwidth, or compatibility.

## ADAN NEXUS | CONNECT console

The existing hourly publisher and public subscription URLs remain at the repository root.
The management application lives in [`apps/nexus/`](apps/nexus/). It reads the published bank;
it does not overwrite the root subscription files or require a server for the hourly workflow.

### Local test (Windows, Linux or macOS)

Install Python 3.12+ and Node.js 22+, clone this repository, then run from its root:

```bash
python apps/nexus/scripts/run_local.py
```

Choose a local administrator email/password when prompted. The launcher creates a private
local configuration, installs dependencies, applies SQLite migrations, imports the checked-out
bank through the normal parser/dedup pipeline, and starts the console at **http://localhost:3000**.
Only loopback ports are opened. Keep the terminal running; Ctrl+C stops the two services.
On Windows, `py -3.12 apps/nexus/scripts/run_local.py` is also supported.

After the initial snapshot import, the local worker polls the public bank every 60 minutes.
GitHub's scheduled refresh and the application's polling are separate clocks; a new bank may
appear in the console on its next poll. For a fresh offline snapshot, run `git pull` while the
launcher is stopped, then restart it. DNS/TCP reachability is never a verified VPN connection.

For self-hosted Docker, deployment gates and recovery, see
[`apps/nexus/docs/DEPLOYMENT.md`](apps/nexus/docs/DEPLOYMENT.md) and
[`apps/nexus/docs/REPOSITORY-INTEGRATION.md`](apps/nexus/docs/REPOSITORY-INTEGRATION.md).
`Nexus verification` runs tests, a frontend production build and a disposable Docker integration
check on application changes. Hourly data-only commits do not trigger application CI.

GitHub Actions does not host the running application. A persistent server or a local computer
is required for the FastAPI/Next.js console; no public deployment is configured by this merge.
