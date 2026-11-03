"""Append the day's MOCI gold and silver reference prices to results/metals/moci_daily.csv. Read only towards MOCI;
one row per MOCI price date (reruns on the same date add nothing). Runs from claude-ops's crontab twice a day.
After about a month the file is compared with the Yahoo based price in the Stock Check tab (gap and correlation).
Command: python3 -I scripts/moci_log.py"""
import csv
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "dashboard"))
import moci  # noqa: E402

OUT = os.path.join(ROOT, "results", "metals", "moci_daily.csv")
COLS = ["moci_date", "logged_at_utc", "k24", "k22", "k21", "k18", "gold_oz", "silver_oz", "platinum_oz"]

p, note = moci.fetch()
if p is None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC: {note}")
    sys.exit(1)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
seen = set()
if os.path.exists(OUT):
    with open(OUT, newline="") as f:
        seen = {r["moci_date"] for r in csv.DictReader(f)}
if p["date"] in seen:
    print(f"{p['date']} already logged")
    sys.exit(0)
new = not os.path.exists(OUT)
with open(OUT, "a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(COLS)
    k, oz = p["karat"], p["ounce"]
    w.writerow([p["date"], f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M}", k.get("24K"), k.get("22K"), k.get("21K"), k.get("18K"),
                oz.get("gold"), oz.get("silver"), oz.get("platinum")])
print(f"logged {p['date']}: 24K {k.get('24K')} KWD per gram")
