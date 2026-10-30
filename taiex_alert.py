#!/usr/bin/env python3
"""Email an alert when TAIEX falls 3%+ below the previous close.

Runs one trading session: checks every 2 minutes from 09:00 to 13:30 Taipei,
then exits. Stdlib only.

Env:
  GMAIL_USER, GMAIL_APP_PASSWORD  sender (and default recipient)
  ALERT_TO        recipient, defaults to GMAIL_USER
  THRESHOLD       percent, default -3.0
  DRY_RUN=1       print emails instead of sending
  ONCE=1          single check right now, ignoring market hours
"""
import json
import os
import smtplib
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

TPE = timezone(timedelta(hours=8))
THRESHOLD = float(os.environ.get("THRESHOLD", "-3.0"))
INTERVAL_S = 120
REMIND_AFTER = timedelta(minutes=60)
FEED_DOWN_AFTER = timedelta(minutes=15)
OPEN = (9, 0)
CLOSE = (13, 31)  # one extra minute to catch the 13:30 closing value
HOLIDAY_CHECK = (9, 10)  # feed still showing an old date by now = no session today

TWSE_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_t00.tw&json=1&delay=0"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII?interval=1d&range=5d"
UA = {"User-Agent": "Mozilla/5.0 (taiex-dip-alert)"}


def log(msg):
    print(f"[{datetime.now(TPE):%H:%M:%S}] {msg}", flush=True)


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def fetch_twse():
    q = get_json(TWSE_URL)["msgArray"][0]
    return {
        "source": "TWSE",
        "date": q["d"],  # YYYYMMDD
        "time": q["t"],
        "price": float(q["z"]),  # "-" before the first tick raises -> fallback
        "prev": float(q["y"]),
        "low": float(q["l"]),
    }


def fetch_yahoo():
    # Yahoo's meta.previousClose can lag a day, so take it from the daily bars.
    res = get_json(YAHOO_URL)["chart"]["result"][0]
    meta = res["meta"]
    ts = datetime.fromtimestamp(meta["regularMarketTime"], TPE)
    day = ts.strftime("%Y%m%d")
    closes = [
        c
        for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"])
        if c is not None and datetime.fromtimestamp(t, TPE).strftime("%Y%m%d") < day
    ]
    return {
        "source": "Yahoo (delayed)",
        "date": day,
        "time": ts.strftime("%H:%M:%S"),
        "price": float(meta["regularMarketPrice"]),
        "prev": float(closes[-1]),
        "low": float(meta.get("regularMarketDayLow") or meta["regularMarketPrice"]),
    }


def fetch():
    for f in (fetch_twse, fetch_yahoo):
        try:
            return f()
        except Exception as e:
            log(f"{f.__name__} failed: {e!r}")
    return None


def send(subject, body):
    if os.environ.get("DRY_RUN"):
        log(f"DRY RUN email: {subject}\n{body}")
        return True
    user = os.environ["GMAIL_USER"]
    msg = EmailMessage()
    msg["Subject"], msg["From"] = subject, user
    msg["To"] = os.environ.get("ALERT_TO") or user
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, os.environ["GMAIL_APP_PASSWORD"])
            s.send_message(msg)
        log(f"sent: {subject}")
        return True
    except Exception as e:
        log(f"email failed: {e!r}")
        return False


def alert(q, pct):
    subject = f"TAIEX {pct:+.2f}% -> {q['price']:,.2f}"
    body = (
        f"TAIEX is {pct:+.2f}% vs. previous close.\n\n"
        f"Now:        {q['price']:,.2f}  ({q['time']} Taipei)\n"
        f"Prev close: {q['prev']:,.2f}\n"
        f"Day low:    {q['low']:,.2f}\n"
        f"Source:     {q['source']}\n"
    )
    return send(subject, body)


def at(now, hm):
    return now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)


def main():
    if os.environ.get("ONCE"):
        q = fetch()
        if not q:
            sys.exit("no data from any source")
        pct = (q["price"] / q["prev"] - 1) * 100
        log(f"{q['source']} {q['date']} {q['time']}: {q['price']:,.2f} ({pct:+.2f}%)")
        if pct <= THRESHOLD:
            alert(q, pct)
        return

    now = datetime.now(TPE)
    if now.weekday() >= 5 or now >= at(now, CLOSE):
        log("market closed, nothing to do")
        return
    if now < at(now, OPEN):
        wait = (at(now, OPEN) - now).total_seconds()
        log(f"waiting {wait:.0f}s for the open")
        time.sleep(wait)

    today = datetime.now(TPE).strftime("%Y%m%d")
    was_below = False
    last_alert = None
    last_ok = datetime.now(TPE)
    feed_warned = False

    while True:
        now = datetime.now(TPE)
        if now >= at(now, CLOSE):
            log("market closed, done")
            return

        q = fetch()
        if q and q["date"] == today:
            last_ok, feed_warned = now, False
            pct = (q["price"] / q["prev"] - 1) * 100
            below = pct <= THRESHOLD
            log(f"{q['source']} {q['time']}: {q['price']:,.2f} ({pct:+.2f}%)")
            # Alert immediately on each new cross below; remind hourly while it stays down.
            if below and (not was_below or now - last_alert >= REMIND_AFTER):
                if alert(q, pct):
                    last_alert = now
                else:
                    below = False  # retry on the next check
            was_below = below
        elif q and now >= at(now, HOLIDAY_CHECK):
            log(f"feed still on {q['date']}, no session today")
            return
        elif not q and now - last_ok >= FEED_DOWN_AFTER and not feed_warned:
            feed_warned = send(
                "TAIEX alert: data feed down",
                f"No TAIEX data from TWSE or Yahoo since {last_ok:%H:%M} Taipei.\n"
                "The watcher keeps retrying, but it can't see the market right now.",
            )

        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    main()
