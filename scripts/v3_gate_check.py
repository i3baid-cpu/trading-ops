"""Read-only MemeSleeveV3 gate check from Binance public klines (no keys). Mirrors MemeSleeveV3.py logic."""
import json, sqlite3, sys, time, urllib.request
from datetime import datetime, timezone

API = "https://api.binance.com/api/v3/klines"
now_ms = int(time.time() * 1000)


def klines(sym, tf, start_ms):
    out = []
    while True:
        url = f"{API}?symbol={sym}&interval={tf}&startTime={start_ms}&limit=1000"
        rows = json.load(urllib.request.urlopen(url, timeout=30))
        out += rows
        if len(rows) < 1000:
            break
        start_ms = rows[-1][0] + 1
    # completed candles only
    return [dict(t=r[0], o=float(r[1]), h=float(r[2]), l=float(r[3]), c=float(r[4]), v=float(r[5]))
            for r in out if r[6] < now_ms]


def ema(vals, n):  # TA-Lib style: seeded with SMA of first n
    res = [None] * len(vals)
    if len(vals) < n:
        return res
    res[n - 1] = sum(vals[:n]) / n
    k = 2 / (n + 1)
    for i in range(n, len(vals)):
        res[i] = vals[i] * k + res[i - 1] * (1 - k)
    return res


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


btc = klines("BTCUSDT", "1d", int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000))
be = ema([r["c"] for r in btc], 100)
btc_up = {r["t"]: int(r["c"] > e) for r, e in zip(btc, be) if e is not None}
DAY = 86400000
L = []
p = L.append
p("# MemeSleeveV3 gate check\n")
p(f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC. Completed candles only.\n")
p("## BTC daily gate\n")
p("| Daily candle | Close | EMA100 | Close vs EMA100 | Gate |\n|---|---|---|---|---|")
for r, e in list(zip(btc, be))[-5:]:
    g = (r["c"] / e - 1) * 100
    p(f"| {ts(r['t'])[:10]} | {r['c']:.2f} | {e:.2f} | {g:+.2f}% | **{'OPEN' if r['c'] > e else 'SHUT'}** |")
p(f"\nBTC 1d history used: {len(btc)} candles from {ts(btc[0]['t'])[:10]} to {ts(btc[-1]['t'])[:10]}.\n")

summary = []
detail = []
for pair in ["DOGE", "PEPE", "SHIB", "FLOKI"]:
    sym = "PEPEUSDT" if pair == "PEPE" else f"{pair}USDT"
    d = klines(sym, "4h", now_ms - 1000 * 4 * 3600 * 1000)
    closes = [r["c"] for r in d]
    e50 = ema(closes, 50)
    rows = []
    for i in range(len(d)):
        hh = max(x["h"] for x in d[i - 20:i]) if i >= 20 else None
        vm = sum(x["v"] for x in d[i - 19:i + 1]) / 20 if i >= 19 else None
        # merge_informative_pair: a 4h candle sees the last daily candle that closed before it closed
        day_open = (d[i]["t"] + 4 * 3600000) // DAY * DAY - DAY
        gate = btc_up.get(day_open)
        ent = bool(gate == 1 and e50[i] and closes[i] > e50[i] and hh and closes[i] > hh and d[i]["v"] > vm and d[i]["v"] > 0)
        rows.append((d[i], e50[i], hh, vm, gate, ent))
    r, e, hh, vm, g, _ = rows[-1]
    fired = [x for x in rows[-3:] if x[5]]
    summary.append(f"| {pair}/USDT | {ts(r['t'])} | {r['c']:.8g} | {e:.8g} | {hh:.8g} | {'yes' if r['c'] > e else 'no'} | "
                   f"{'yes' if r['c'] > hh else 'no'} | {'yes' if fired else 'no'} |")
    detail.append(f"\n### {pair}/USDT\n\n| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |\n|---|---|---|---|---|---|---|---|---|")
    for r, e, hh, vm, g, ent in rows[-3:]:
        detail.append(f"| {ts(r['t'])} | {r['c']:.8g} | {e:.8g} | {hh:.8g} | {'yes' if r['v'] > vm else 'no'} | "
                      f"{'open' if g else 'shut'} | {'yes' if r['c'] > e else 'no'} | {'yes' if r['c'] > hh else 'no'} | **{'YES' if ent else 'no'}** |")
    # last time an entry would have fired in the fetched window
    last = [x for x in rows if x[5]]
    summary_last = ts(last[-1][0]["t"]) if last else "none in window"
    detail.append(f"\nLast entry signal in the fetched window ({ts(d[0]['t'])} to {ts(d[-1]['t'])}): {summary_last}.")

p("## Pairs, last completed 4h candle\n")
p("| Pair | Candle (UTC open) | Close | EMA50 | Prior 20 bar high | Close>EMA50 | Close>HH20 | Entry fired in last 3 |\n|---|---|---|---|---|---|---|---|")
L += summary
p("\n## Entry conditions on the last three 4h candles")
L += detail

c = sqlite3.connect("file:/root/freqtrade/user_data/tradesv3.dryrun.sqlite?mode=ro", uri=True)
op = c.execute("select id,pair,strategy,open_date,open_rate from trades where is_open=1").fetchall()
p("\n## Dry run: open trades\n")
p("\n".join(f"- {x}" for x in op) if op else "_None._")
n = c.execute("select count(*) from trades where strategy='MemeSleeveV3'").fetchone()[0]
p(f"\nMemeSleeveV3 trades in the dry run database, all time: {n}.")
p("\n## Provenance\n")
p("Data: Binance spot public klines API (no keys), BTCUSDT 1d from 2023-01-01, DOGE/PEPE/SHIB/FLOKI USDT 4h last 1000 candles.")
p("EMA computed TA-Lib style (SMA seed); BTC gate mapped to 4h candles as merge_informative_pair does (previous completed day).")
p("Freqtrade's own data dir was not touched (claude-ops uses docker for read-only commands only).")
p(f"Command: `python3 -I {sys.argv[0]}`")
print("\n".join(L))
