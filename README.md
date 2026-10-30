# taiex-dip-alert

Emails you when TAIEX (發行量加權股價指數) is down 3%+ vs. the previous close.

- Runs on GitHub Actions every trading day from 08:50 Taipei; checks every 2 minutes until 13:30.
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

## Test

```bash
DRY_RUN=1 ONCE=1 python3 taiex_alert.py
```

Or Actions → *TAIEX dip watch* → Run workflow (`once` checked).

## Notes

- GitHub disables scheduled workflows after 60 days without repo activity; it emails you first — re-enable from the Actions tab.
- Not financial advice.
