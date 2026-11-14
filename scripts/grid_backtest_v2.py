#!/usr/bin/env python3
"""
Spot grid backtester, version 2. PROPOSAL from results/fable_review_2026-11-14.md; research only, read only.

scripts/grid_backtest.py (version 1) is left untouched because results/research_grid.md was produced with it.
This file fixes the chronology and accounting defects listed in the review and must be reported as a new
simulator version, never as a correction of the old numbers.

  python3 scripts/grid_backtest_v2.py --all --out-dir results/grid_v2     # 6 fixed candidates, windows A and B,
                                                                          # both intrabar paths, net and gross recentre
  python3 scripts/grid_backtest_v2.py --pair BTCUSDT --range R1 --levels 40 --break K2 --start 2020-01-01 \
      --end 2023-10-30 --window-start 2020-08-15 --path OHLC --recentre gross --out results/grid_v2/one.json

What changed against version 1 (finding ids from docs/INDEPENDENT_AUDIT_FINDINGS_2026-11-14.md):
  G-N1/N3  Every decision (create, recentre, stop, re-entry) is taken at the close of candle i from data up to
           and including i, and is executed at the OPEN of candle i+1. Orders can only fill from then on.
  G-N2     The per level budget is capital / (n * (1 + fee)), so every buy and its fee is funded. Cash can never
           go below zero; the code asserts it.
  G-N4     Equity is marked at every vertex of the intrabar path. Drawdown is reported twice: closes only and
           intrabar.
  G-N5     Priority at a close is fixed: K2 stop on the active grid, then K3, then the scheduled recentre.
  G-N6/N7  One ledger for the whole run: grid spread profit, liquidation profit, open profit and fees. They must
           add up to equity on every candle (asserted). Fees are booked when they are paid.
  G-N8     The month key is set at every grid creation.
  G-N9/K4  No last_idx. Price walks an explicit path through each candle, open low high close (OLHC) or open high
           low close (OHLC). A level fills when the path crosses it. Run both paths; the truth lies between.
  G-N10    K1 is defined as: resting orders stay live and fill whenever the path crosses them; nothing is closed
           and nothing is recentred because of a break.
  G-K1     Recentre trades are charged. --recentre net charges the fee on the difference between old and new
           inventory (cancel orders, trade the difference). --recentre gross charges both legs (sell all, rebuy).
  G-K2     Follows from the single ledger.
  G-K3     K3 recentres under R2 as well.
Kept on purpose so that differences are bug fixes only: range rules, the 2% recentre threshold, the K2 stop tested
on hourly closes, the K2 re-entry count, fills at the level price on touch, fee per side.
"""
from __future__ import annotations

import argparse, json, os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid_backtest import CANDIDATES, WINDOWS, load_klines, range_for, sma, ts   # unchanged version 1 helpers

VERSION = "grid_backtest_v2 2026-11-14"
EPS = 1e-9
DAY = 86_400_000


class Ledger:
    """Profit components for a whole run. equity == capital + grid_realized + liquidation_pnl + open_pnl - fees."""

    def __init__(self, capital: float):
        self.capital = capital
        self.grid_realized = 0.0      # level to level sales: proceeds minus cost of the lot
        self.liquidation_pnl = 0.0    # lots closed by a stop or a recentre: proceeds minus cost
        self.fees = 0.0
        self.fills: list[tuple] = []  # (t, side, level index or None, price, coins)
        self.events: list[tuple] = [] # (t, kind, detail)


class Grid:
    def __init__(self, lo: float, hi: float, n: int, cash: float, coins: float, price: float, fee: float,
                 ledger: Ledger, t: int, recentre: str = "net"):
        if not hi > lo > 0:
            raise ValueError(f"bad range {lo}..{hi}")
        self.lo, self.hi, self.n, self.fee, self.led, self.created_t = lo, hi, n, fee, ledger, t
        self.levels = [lo + i * (hi - lo) / n for i in range(n + 1)]
        equity = cash + coins * price
        self.per_level = equity / (n * (1 + fee))          # G-N2: all n buys and their fees fit into equity
        self.lots: dict[int, tuple[float, float]] = {}     # level index -> (coins, cost in USDT)
        self.cash = equity                                 # value everything at price, then buy the target back
        target_idx = [i for i in range(n) if self.levels[i] >= price]
        target_coins = len(target_idx) * self.per_level / price
        traded = (coins + target_coins) if recentre == "gross" else abs(target_coins - coins)
        self._fee(traded * price)
        for i in target_idx:
            self.lots[i] = (self.per_level / price, self.per_level)
            self.cash -= self.per_level
        if target_coins > coins + EPS:
            ledger.fills.append((t, "buy", None, price, target_coins - coins))
        elif coins > target_coins + EPS:
            ledger.fills.append((t, "sell", None, price, coins - target_coins))
        self.pos = price
        assert self.cash >= -EPS * max(1.0, equity), f"negative cash {self.cash}"

    def _fee(self, usdt: float):
        f = usdt * self.fee
        self.cash -= f
        self.led.fees += f

    def move(self, to: float, t: int):
        """Walk the price from self.pos to `to`. Buy level i when the walk crosses it downward, sell lot i when
        the walk crosses level i+1 upward. Fills are at the level price."""
        a = self.pos
        if to < a:
            for i in range(self.n - 1, -1, -1):
                L = self.levels[i]
                if to <= L < a and i not in self.lots and self.cash >= self.per_level * (1 + self.fee) - EPS:
                    self.lots[i] = (self.per_level / L, self.per_level)
                    self.cash -= self.per_level
                    self._fee(self.per_level)
                    self.led.fills.append((t, "buy", i, L, self.per_level / L))
        elif to > a:
            for i in range(self.n):
                U = self.levels[i + 1]
                if a < U <= to and i in self.lots:
                    coins, cost = self.lots.pop(i)
                    proceeds = coins * U
                    self.cash += proceeds
                    self._fee(proceeds)
                    self.led.grid_realized += proceeds - cost
                    self.led.fills.append((t, "sell", i, U, coins))
        self.pos = to
        assert self.cash >= -EPS * max(1.0, self.per_level * self.n), f"negative cash {self.cash}"

    def inventory(self) -> float:
        return sum(c for c, _ in self.lots.values())

    def cost(self) -> float:
        return sum(c for _, c in self.lots.values())

    def close_lots(self, price: float) -> float:
        """Book every open lot as closed at `price` (no fee here). Returns the coins that were held."""
        coins = self.inventory()
        self.led.liquidation_pnl += coins * price - self.cost()
        self.cash += coins * price
        self.lots.clear()
        return coins

    def liquidate(self, price: float, t: int) -> float:
        """Sell everything at `price`, pay the fee, return the cash."""
        coins = self.close_lots(price)
        self._fee(coins * price)
        if coins > EPS:
            self.led.fills.append((t, "sell", None, price, coins))
        return self.cash

    def equity(self, price: float) -> float:
        return self.cash + self.inventory() * price

    def open_pnl(self, price: float) -> float:
        return self.inventory() * price - self.cost()


def _month(t: int) -> tuple[int, int]:
    d = datetime.fromtimestamp(t / 1000, tz=timezone.utc)
    return d.year, d.month


def run(pair: str, rule: str, n: int, brk: str, capital: float, fee: float, start: str, end: str, wstart: str,
        path: str = "OLHC", recentre: str = "net", check: bool = True, return_ledger: bool = False) -> dict:
    assert path in ("OLHC", "OHLC") and recentre in ("net", "gross") and brk in ("K1", "K2", "K3")
    kl = load_klines(pair, start, end)
    for a, b in zip(kl, kl[1:]):
        assert b["t"] > a["t"], "candles out of order"
    closes = [k["c"] for k in kl]
    w0 = max(1, next(i for i, k in enumerate(kl) if k["t"] >= ts(wstart)))
    led = Ledger(capital)
    grid: Grid | None = None
    cash_only: float | None = None        # after a K2 stop
    started = False
    month_key = None
    paused_since = None
    above_sma_days = 0
    restarts = 0
    pending: tuple | None = None          # decision taken at the previous close, executed at this open
    peak_c = peak_i = capital
    dd_close = dd_intra = 0.0
    eq_curve: list[tuple[int, float]] = []

    def decide(i: int):
        """Decision at the close of candle i, from data up to and including i. Returns the action for i+1's open."""
        nonlocal month_key, paused_since, above_sma_days
        k = kl[i]; p = k["c"]
        rng = range_for(rule, kl, i, closes)
        if rng is None or not rng[1] > rng[0]:
            return None
        nxt_month = _month(kl[i + 1]["t"]) if i + 1 < len(kl) else _month(k["t"])
        if grid is None and not started:
            return ("create", rng)
        if grid is not None:
            if brk == "K2" and p < grid.lo * 0.90:                         # 1. stop on the grid that is live now
                return ("stop",)
            outside = p < grid.lo or p > grid.hi
            if brk == "K3" and outside:                                    # 2. immediate recentre, every range rule
                return ("recentre", rng)
            if rule == "R1" and nxt_month != month_key:                    # 3. scheduled recentres
                month_key = nxt_month
                moved = abs(grid.lo - rng[0]) / grid.lo > 0.02 or abs(grid.hi - rng[1]) / grid.hi > 0.02
                if brk == "K3" or moved:
                    return ("recentre", rng)
            elif rule == "R2":
                if outside:
                    paused_since = paused_since or k["t"]
                    if k["t"] - paused_since >= DAY:
                        paused_since = None
                        return ("recentre", rng)
                else:
                    paused_since = None
            return None
        # cash only after a K2 stop: wait for 5 daily marks above the 200 day average (version 1 rule, unchanged)
        m = sma(closes, 200 * 24, i)
        if m and p > m and k["t"] % DAY == 0:
            above_sma_days += 1
        elif m and p <= m:
            above_sma_days = 0
        if above_sma_days >= 5:
            return ("create", rng)
        return None

    pending = decide(w0 - 1)
    for i in range(w0, len(kl)):
        k = kl[i]; t = k["t"]; o = k["o"]
        # 1. execute the decision taken at the previous close, at this candle's open
        if pending:
            kind = pending[0]
            if kind == "create":
                lo, hi = pending[1]
                cash = capital if not started else cash_only
                grid = Grid(lo, hi, n, cash, 0.0, o, fee, led, t, recentre)
                started = True; cash_only = None; restarts += 1; above_sma_days = 0
                month_key = _month(t)                                      # G-N8
            elif kind == "stop":
                cash_only = grid.liquidate(o, t); grid = None; above_sma_days = 0; paused_since = None
            elif kind == "recentre":
                lo, hi = pending[1]
                coins = grid.close_lots(o)
                grid = Grid(lo, hi, n, grid.cash - coins * o, coins, o, fee, led, t, recentre)
                restarts += 1
                month_key = _month(t)
            led.events.append((t, kind, pending[1] if len(pending) > 1 else None))
            pending = None
        # 2. walk the candle; only orders that existed at the open can fill
        marks = []
        if grid is not None:
            pts = [o, k["l"], k["h"], k["c"]] if path == "OLHC" else [o, k["h"], k["l"], k["c"]]
            for x in pts:
                grid.move(x, t)
                marks.append(grid.equity(x))
            eq = grid.equity(k["c"])
            if check:
                parts = capital + led.grid_realized + led.liquidation_pnl + grid.open_pnl(k["c"]) - led.fees
                assert abs(parts - eq) < 1e-6 * capital, (t, parts, eq)
        else:
            eq = cash_only if cash_only is not None else capital
            marks.append(eq)
            if check:
                assert abs(capital + led.grid_realized + led.liquidation_pnl - led.fees - eq) < 1e-6 * capital
        # 3. drawdown, on closes and on every intrabar mark
        for m_ in marks:
            dd_intra = max(dd_intra, (peak_i - m_) / peak_i)
            peak_i = max(peak_i, m_)
        dd_close = max(dd_close, (peak_c - eq) / peak_c)
        peak_c = max(peak_c, eq)
        eq_curve.append((t, eq))
        # 4. decide at the close for the next open
        if i + 1 < len(kl):
            pending = decide(i)

    final = eq_curve[-1][1]
    last = kl[-1]["c"]
    inv = grid.inventory() if grid is not None else 0.0
    open_pnl = grid.open_pnl(last) if grid is not None else 0.0
    years = (kl[-1]["t"] - kl[w0]["t"]) / (365.25 * DAY)
    hold = capital * last / kl[w0]["o"]
    q = {}
    for t, e in eq_curve:
        d = datetime.fromtimestamp(t / 1000, tz=timezone.utc); q[f"{d.year}Q{(d.month - 1) // 3 + 1}"] = e
    qpnl, prev = {}, capital
    for key in sorted(q):
        qpnl[key] = q[key] - prev; prev = q[key]
    best_q = max(qpnl.values()) if qpnl else 0
    out = {
        "simulator": VERSION, "pair": pair, "range": rule, "levels": n, "break": brk, "capital": capital, "fee": fee,
        "window": [wstart, end], "path": path, "recentre_fee": recentre,
        "final_equity_mtm": round(final, 2), "final_equity_if_liquidated": round(final - inv * last * fee, 2),
        "total_return_pct": round((final / capital - 1) * 100, 2),
        "annualised_pct": round(((final / capital) ** (1 / years) - 1) * 100, 2) if years > 0 else None,
        "max_drawdown_close_pct": round(dd_close * 100, 2), "max_drawdown_intrabar_pct": round(dd_intra * 100, 2),
        "grid_realized": round(led.grid_realized, 2), "liquidation_pnl": round(led.liquidation_pnl, 2),
        "open_pnl_at_end": round(open_pnl, 2), "fees": round(led.fees, 2),
        "reconciles": abs(capital + led.grid_realized + led.liquidation_pnl + open_pnl - led.fees - final) < 1e-6 * capital,
        "fills": len(led.fills), "restarts": restarts,
        "events": {kind: sum(1 for e in led.events if e[1] == kind) for kind in ("create", "recentre", "stop")},
        "buy_and_hold_final": round(hold, 2), "buy_and_hold_pct": round((hold / capital - 1) * 100, 2),
        "best_quarter_share": round(best_q / (final - capital), 2) if abs(final - capital) > EPS else None,
        "quarters": {k_: round(v, 2) for k_, v in qpnl.items()},
    }
    if return_ledger:
        out["_ledger"] = led
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair"); ap.add_argument("--range", default="R1"); ap.add_argument("--levels", type=int, default=20)
    ap.add_argument("--break", dest="brk", default="K1"); ap.add_argument("--capital", type=float, default=3000)
    ap.add_argument("--fee", type=float, default=0.001); ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end"); ap.add_argument("--window-start"); ap.add_argument("--out")
    ap.add_argument("--path", default="OLHC", choices=["OLHC", "OHLC"])
    ap.add_argument("--recentre", default="net", choices=["net", "gross"])
    ap.add_argument("--all", action="store_true"); ap.add_argument("--out-dir", default="results/grid_v2")
    a = ap.parse_args()
    if a.all:
        os.makedirs(a.out_dir, exist_ok=True)
        table = []
        for W, (ws, we) in WINDOWS.items():
            for pair, rule, n, brk in CANDIDATES:
                for path in ("OLHC", "OHLC"):
                    for rc in ("net", "gross"):
                        r = run(pair, rule, n, brk, a.capital, a.fee, "2020-01-01" if W == "A" else "2023-01-01", we, ws, path, rc)
                        r["window_name"] = W; table.append(r)
                        with open(os.path.join(a.out_dir, f"{pair}_{rule}_{n}_{brk}_{W}_{path}_{rc}.json"), "w") as fh:
                            json.dump(r, fh, indent=1)
                        print(f"{W} {pair} {rule} N={n} {brk} {path} {rc}: {r['total_return_pct']:+.1f}% "
                              f"DD close {r['max_drawdown_close_pct']:.1f}% intrabar {r['max_drawdown_intrabar_pct']:.1f}% "
                              f"reconciles {r['reconciles']}")
        with open(os.path.join(a.out_dir, "summary.json"), "w") as fh:
            json.dump(table, fh, indent=1)
        return
    r = run(a.pair, a.range, a.levels, a.brk, a.capital, a.fee, a.start, a.end, a.window_start or a.start, a.path, a.recentre)
    print(json.dumps(r, indent=1))
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w") as fh:
            json.dump(r, fh, indent=1)


if __name__ == "__main__":
    main()
