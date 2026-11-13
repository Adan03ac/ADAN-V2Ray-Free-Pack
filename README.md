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
