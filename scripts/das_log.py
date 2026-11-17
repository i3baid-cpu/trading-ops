"""Append Dar Al Sabaek's live gold buy and sell prices to results/metals/das_daily.csv. Read only towards the dealer;
one row per run, stamped with the time it was read (the reply carries no time of its own). Runs from claude-ops's
crontab at 06:30 and 18:30 UTC; the open item 8 comparison matches each row with Yahoo's GC=F x KWD=X price for the
same day. Replaces scripts/moci_log.py (MOCI blocks scripts since 10 Nov 2026).
Command: python3 -I scripts/das_log.py"""
import csv
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
import daralsabaek as das  # noqa: E402

OUT = os.path.join(ROOT, "results", "metals", "das_daily.csv")
COLS = ["logged_at_utc", "buy24", "buy22", "buy21", "buy18", "sell24", "sell22", "sell21", "sell18", "gold_oz_usd", "gold_status"]

p, note = das.fetch()
if p is None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: {note}")
    sys.exit(1)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
new = not os.path.exists(OUT)
with open(OUT, "a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(COLS)
    b, s = p["buy"], p["sell"]
    w.writerow([p["time"].removesuffix(" UTC")] + [round(b[k], 3) for k in das.KARATS] + [round(s[k], 3) for k in das.KARATS]
               + [p["gold_oz_usd"], p["status"]])
print(f"logged {p['time']}: 24K buy {b['24K']:.3f} sell {s['24K']:.3f} KWD per gram")
