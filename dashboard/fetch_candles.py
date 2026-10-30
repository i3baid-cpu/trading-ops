"""
Optional: download real 5m OHLC candles for the Freqtrade pairs from Binance's
PUBLIC market-data endpoint (no API key, no account, read-only) so the Trade
Explorer can draw candlesticks with buy/sell markers.

    python fetch_candles.py            # DOGE PEPE SHIB FLOKI, Oct 29-31 2026
    python fetch_candles.py DOGEUSDT 2026-10-29 2026-10-31

Writes data/candles/<PAIR>_5m.csv. Nothing is written anywhere else and no
order endpoint is ever called.
"""
import csv, json, os, sys, time, urllib.request
from datetime import datetime, timezone

PAIRS = ["DOGEUSDT", "PEPEUSDT", "SHIBUSDT", "FLOKIUSDT"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "candles")
BASE = "https://api.binance.com/api/v3/klines"


def fetch(pair, start, end):
    t0 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
    t1 = int(datetime.fromisoformat(end).replace(tzinfo=timezone.utc).timestamp() * 1000)
    rows = []
    while t0 < t1:
        url = f"{BASE}?symbol={pair}&interval=5m&startTime={t0}&endTime={t1}&limit=1000"
        with urllib.request.urlopen(url, timeout=30) as r:
            batch = json.load(r)
        if not batch:
            break
        rows += batch
        t0 = batch[-1][0] + 300_000
        time.sleep(0.2)
    return rows


def main():
    args = sys.argv[1:]
    pairs = [args[0]] if args else PAIRS
    start = args[1] if len(args) > 1 else "2026-10-29"
    end = args[2] if len(args) > 2 else "2026-10-31"
    os.makedirs(OUT, exist_ok=True)
    for p in pairs:
        rows = fetch(p, start, end)
        path = os.path.join(OUT, f"{p}_5m.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["open_time", "open", "high", "low", "close", "volume"])
            for k in rows:
                w.writerow([datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(), k[1], k[2], k[3], k[4], k[5]])
        print(f"{p}: {len(rows)} candles -> {path}")


if __name__ == "__main__":
    main()
