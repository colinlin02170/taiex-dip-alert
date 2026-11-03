# taiex-dip-alert

Emails you when TAIEX (發行量加權股價指數) is down 3%+ vs. the previous close.

- Runs on GitHub Actions every trading day from 08:50 Taipei; checks every 2 minutes until 13:30.
- Started by cron-job.org via the `workflow_dispatch` API (GitHub's own `schedule` is a best-effort backup that can be hours late).
- Sends a "watch started" email each trading morning — no email means it isn't running.
- Emails on each new drop below -3%, then hourly while it stays down.
- Data: TWSE MIS feed, Yahoo Finance `^TWII` as backup. Warns by email if both are down for 15 minutes.
- Holidays are skipped automatically.

## Setup

1. Create a Gmail app password (needs 2-step verification): https://myaccount.google.com/apppasswords
2. Add repo secrets:

   ```bash
   gh secret set GMAIL_USER
   gh secret set GMAIL_APP_PASSWORD
   ```

   Optional: `gh secret set ALERT_TO` to send somewhere other than `GMAIL_USER`.

3. Daily trigger on https://cron-job.org (Asia/Taipei, 08:50, Mon-Fri):
   - `POST https://api.github.com/repos/colinlin02170/taiex-dip-alert/actions/workflows/watch.yml/dispatches`
   - Headers: `Authorization: Bearer <fine-grained token, this repo only, Actions: read & write>`,
     `Accept: application/vnd.github+json`, `Content-Type: application/json`
   - Body: `{"ref":"main","inputs":{"once":"false"}}` — success is HTTP 204.

## Test

```bash
DRY_RUN=1 ONCE=1 python3 taiex_alert.py
```

Or Actions → *TAIEX dip watch* → Run workflow (`once` checked).

## Notes

- GitHub disables scheduled workflows after 60 days without repo activity; it emails you first — re-enable from the Actions tab.
- Not financial advice.
