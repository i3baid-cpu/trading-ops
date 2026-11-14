#!/usr/bin/env python3
"""
Spot grid backtester for docs/RESEARCH_GRID_PLAN.md. Read only; Binance public klines, no keys.

  python3 scripts/grid_backtest.py --pair BTCUSDT --start 2020-01-01 --end 2023-10-30 --window-start 2020-08-15 \
      --range R1 --levels 20 --break K1 --capital 3000 --fee 0.001 --out results/grid/btc_R1_20_K1_A.json
  python3 scripts/grid_backtest.py --all --out-dir results/grid      # the 6 fixed candidates on windows A and B

Mechanics are the ones written in the plan: arithmetic grid, equal USDT per level, starting inventory for levels
above price, buy on crossing a level downward, sell the lot from one level below on crossing upward, fee per side,
equity = cash + inventory at close. Candles are cached under data/klines/ so repeat runs do not hit the API.
"""
from __future__ import annotations

import argparse, csv, json, math, os, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "..", "data", "klines")
BINANCE = "https://api.binance.com/api/v3/klines"
WINDOWS = {"A": ("2020-08-15", "2023-10-30"), "B": ("2023-10-30", "2026-10-30")}
CANDIDATES = [  # fixed in the plan; do not add after seeing results
    ("BTCUSDT", "R1", 20, "K1"), ("BTCUSDT", "R2", 20, "K2"), ("ETHUSDT", "R1", 20, "K1"),
    ("BTCUSDT", "R1", 40, "K2"), ("BTCUSDT", "R2", 20, "K3"), ("ETHUSDT", "R2", 20, "K2"),
]


def ts(s: str) -> int:
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)


def load_klines(pair: str, start: str, end: str, interval: str = "1h") -> list[dict]:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{pair}_{interval}_{start}_{end}.csv")
    if os.path.exists(path):
        with open(path) as fh:
            return [{k: (float(v) if k != "t" else int(v)) for k, v in r.items()} for r in csv.DictReader(fh)]
    rows, t0, t1 = [], ts(start), ts(end)
    while t0 < t1:
        url = f"{BINANCE}?symbol={pair}&interval={interval}&startTime={t0}&endTime={t1}&limit=1000"
        with urllib.request.urlopen(url, timeout=30) as r:
            batch = json.load(r)
        if not batch:
            break
        rows += [{"t": k[0], "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in batch]
        t0 = batch[-1][0] + 1
        time.sleep(0.15)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["t", "o", "h", "l", "c", "v"]); w.writeheader(); w.writerows(rows)
    return rows


# --------------------------------------------------------------------------- #
class Grid:
    def __init__(self, lo: float, hi: float, n: int, capital: float, price: float, fee: float):
        self.lo, self.hi, self.n, self.fee = lo, hi, n, fee
        self.levels = [lo + i * (hi - lo) / n for i in range(n + 1)]
        self.per_level = capital / n                      # USDT committed per level
        self.lots: dict[int, float] = {}                  # level index -> coins held bought at that level
        self.cash = capital
        self.realized = 0.0
        self.fees = 0.0
        # starting inventory: one lot for each level at or above price (bought at current price)
        for i, lv in enumerate(self.levels[:-1]):
            if lv >= price:
                coins = self.per_level / price
                self.lots[i] = coins
                self.cash -= self.per_level
                self._fee(self.per_level)
        self.last_idx = self._idx(price)

    def _fee(self, usdt: float):
        f = usdt * self.fee
        self.cash -= f
        self.fees += f

    def _idx(self, p: float) -> int:
        return max(0, min(self.n, int((p - self.lo) / ((self.hi - self.lo) / self.n))))

    def step(self, low: float, high: float):
        """Process one candle: buys on the way down to `low`, sells on the way up to `high` (order: down then up)."""
        for i in range(self.last_idx - 1, -1, -1):          # crossing levels downward
            if low <= self.levels[i] and i not in self.lots and self.cash >= self.per_level * (1 + self.fee):
                self.lots[i] = self.per_level / self.levels[i]
                self.cash -= self.per_level
                self._fee(self.per_level)
        for i in range(0, self.n):                            # crossing levels upward: sell lot i at level i+1
            if high >= self.levels[i + 1] and i in self.lots:
                coins = self.lots.pop(i)
                proceeds = coins * self.levels[i + 1]
                self.cash += proceeds
                self._fee(proceeds)
                self.realized += proceeds - self.per_level
        self.last_idx = self._idx(high if high < self.hi else low)

    def inventory(self) -> float:
        return sum(self.lots.values())

    def liquidate(self, price: float):
        coins = self.inventory()
        proceeds = coins * price
        self.cash += proceeds
        self._fee(proceeds)
        self.lots.clear()
        return proceeds

    def equity(self, price: float) -> float:
        return self.cash + self.inventory() * price


def sma(closes: list[float], n: int, i: int) -> float | None:
    return sum(closes[i - n + 1:i + 1]) / n if i + 1 >= n else None


def range_for(rule: str, kl: list[dict], i: int, closes: list[float]) -> tuple[float, float] | None:
    if rule in ("R1", "R3"):
        lookback = kl[max(0, i - 90 * 24):i + 1]
        return min(k["l"] for k in lookback), max(k["h"] for k in lookback)
    if rule == "R2":
        m = sma(closes, 200 * 24, i)
        return (m * 0.8, m * 1.2) if m else None
    raise ValueError(rule)


def run(pair: str, rule: str, n: int, brk: str, capital: float, fee: float, start: str, end: str, wstart: str) -> dict:
    kl = load_klines(pair, start, end)
    closes = [k["c"] for k in kl]
    w0 = next(i for i, k in enumerate(kl) if k["t"] >= ts(wstart))
    grid: Grid | None = None
    paused_since = None
    eq_curve, peak, max_dd = [], 0.0, 0.0
    cash_only = None                       # after K2 stop: cash held until re-entry condition
    above_sma_days = 0
    realized_total = fees_total = 0.0
    month_key = None
    restarts = 0
    for i in range(w0, len(kl)):
        k = kl[i]; p = k["c"]; day = datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc)
        rng = range_for(rule, kl, i, closes)
        if rng is None:
            continue
        lo, hi = rng
        if grid is None and cash_only is None:
            grid = Grid(lo, hi, n, capital, p, fee); restarts += 1
            month_key = (day.year, day.month)
        # recentre rules
        if grid is not None:
            if rule == "R1" and (day.year, day.month) != month_key and k["t"] % 86_400_000 == 0:
                month_key = (day.year, day.month)
                cap = grid.equity(p); realized_total += grid.realized; fees_total += grid.fees
                if brk == "K3" or abs(grid.lo - lo) / grid.lo > 0.02 or abs(grid.hi - hi) / grid.hi > 0.02:
                    grid.liquidate(p) if brk == "K3" else None
                    # K1/K2: carry inventory into the new grid by valuing it at market and restarting
                    cap = grid.equity(p); grid.liquidate(p)
                    grid = Grid(lo, hi, n, cap, p, fee); restarts += 1
            elif rule == "R2":
                outside = p < grid.lo or p > grid.hi
                if outside:
                    paused_since = paused_since or k["t"]
                    if k["t"] - paused_since >= 24 * 3_600_000:
                        cap = grid.equity(p); realized_total += grid.realized; fees_total += grid.fees
                        grid.liquidate(p); grid = Grid(lo, hi, n, cap, p, fee); restarts += 1; paused_since = None
                else:
                    paused_since = None
        # break rules
        if grid is not None:
            if p < grid.lo or p > grid.hi:
                if brk == "K2" and p < grid.lo * 0.90:
                    realized_total += grid.realized; fees_total += grid.fees
                    grid.liquidate(p); cash_only = grid.cash; grid = None; above_sma_days = 0
                elif brk == "K3" and rule != "R2":
                    cap = grid.equity(p); realized_total += grid.realized; fees_total += grid.fees
                    grid.liquidate(p); grid = Grid(lo, hi, n, cap, p, fee); restarts += 1
                # K1: pause (step still runs but nothing crosses while outside)
            grid.step(k["l"], k["h"]) if grid is not None else None
        elif cash_only is not None:
            m = sma(closes, 200 * 24, i)
            if m and p > m and k["t"] % 86_400_000 == 0:
                above_sma_days += 1
            elif m and p <= m:
                above_sma_days = 0
            if above_sma_days >= 5:
                grid = Grid(lo, hi, n, cash_only, p, fee); restarts += 1; cash_only = None
        eq = grid.equity(p) if grid is not None else cash_only
        eq_curve.append((k["t"], eq))
        peak = max(peak, eq); max_dd = max(max_dd, (peak - eq) / peak if peak else 0)
    final = eq_curve[-1][1]
    if grid is not None:
        realized_total += grid.realized; fees_total += grid.fees
    years = (kl[-1]["t"] - kl[w0]["t"]) / (365.25 * 86_400_000)
    hold = capital * kl[-1]["c"] / kl[w0]["c"]
    # quarter contribution
    q = {}
    prev = capital
    for t, e in eq_curve:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc); key = f"{d.year}Q{(d.month - 1) // 3 + 1}"
        q[key] = e
    qpnl, last = {}, capital
    for key in sorted(q):
        qpnl[key] = q[key] - last; last = q[key]
    best_q = max(qpnl.values()) if qpnl else 0
    return {
        "pair": pair, "range": rule, "levels": n, "break": brk, "capital": capital, "fee": fee, "window": [wstart, end],
        "final_equity": round(final, 2), "total_return_pct": round((final / capital - 1) * 100, 2),
        "annualised_pct": round(((final / capital) ** (1 / years) - 1) * 100, 2) if years > 0 else None,
        "max_drawdown_pct": round(max_dd * 100, 2), "realized_grid_profit": round(realized_total, 2), "fees": round(fees_total, 2),
        "inventory_mtm_at_end": round(final - capital - realized_total + fees_total, 2),
        "buy_and_hold_final": round(hold, 2), "buy_and_hold_pct": round((hold / capital - 1) * 100, 2),
        "restarts": restarts, "best_quarter_share": round(best_q / (final - capital), 2) if final != capital else None,
        "quarters": {k: round(v, 2) for k, v in qpnl.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair"); ap.add_argument("--range", default="R1"); ap.add_argument("--levels", type=int, default=20)
    ap.add_argument("--break", dest="brk", default="K1"); ap.add_argument("--capital", type=float, default=3000)
    ap.add_argument("--fee", type=float, default=0.001); ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end"); ap.add_argument("--window-start"); ap.add_argument("--out"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--out-dir", default="results/grid")
    a = ap.parse_args()
    if a.all:
        os.makedirs(a.out_dir, exist_ok=True)
        table = []
        for W, (ws, we) in WINDOWS.items():
            for pair, rule, n, brk in CANDIDATES:
                r = run(pair, rule, n, brk, a.capital, a.fee, "2020-01-01" if W == "A" else "2023-01-01", we, ws)
                r["window_name"] = W; table.append(r)
                with open(os.path.join(a.out_dir, f"{pair}_{rule}_{n}_{brk}_{W}.json"), "w") as fh:
                    json.dump(r, fh, indent=1)
                print(f"{W} {pair} {rule} N={n} {brk}: total {r['total_return_pct']:+.1f}% ann {r['annualised_pct']:+.1f}% "
                      f"maxDD {r['max_drawdown_pct']:.1f}% realized {r['realized_grid_profit']:+.0f} inventory {r['inventory_mtm_at_end']:+.0f} "
                      f"fees {r['fees']:.0f} | hold {r['buy_and_hold_pct']:+.1f}%")
        with open(os.path.join(a.out_dir, "summary.json"), "w") as fh:
            json.dump(table, fh, indent=1)
        return
    r = run(a.pair, a.range, a.levels, a.brk, a.capital, a.fee, a.start, a.end, a.window_start or a.start)
    print(json.dumps(r, indent=1))
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        with open(a.out, "w") as fh:
            json.dump(r, fh, indent=1)


if __name__ == "__main__":
    main()
