"""Reproductions of the grid findings against the UNCHANGED scripts/grid_backtest.py (blob b78026a, version 1).
Evidence for results/fable_review_2026-11-14.md. Synthetic candles, no network, nothing is modified.
Each block asserts the defective behaviour, so this file PASSES while version 1 has the defect.
Run: python3 scripts/tests/repro_grid_v1_findings.py"""
import os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import grid_backtest as G

H = 3_600_000
T0 = 1_598_918_400_000          # 2020-09-01 00:00 UTC
SEP = 30 * 24
REAL_GRID, REAL_RANGE = G.Grid, G.range_for


def kl(rows, t0=T0):
    return [{"t": t0 + i * H, "o": o, "h": h, "l": l, "c": c, "v": 1.0} for i, (o, h, l, c) in enumerate(rows)]


def flat(n, p=100.0):
    return [(p, p, p, p)] * n


def run_on(rows, rule, n, brk, wstart="2020-09-01 12:00", t0=T0, capital=1000, fee=0.001):
    candles = kl(rows, t0)
    G.load_klines = lambda pair, start, end, interval="1h": candles
    return G.run("SYN", rule, n, brk, capital, fee, "2020-01-01", "2030-01-01", wstart)


WICKS = flat(10) + [(100, 110, 100, 100), (100, 100, 90, 100)]      # gives R1 a 90..110 range

# ---- G-N1 --------------------------------------------------------------------------------------------------------
g = G.Grid(90, 110, 4, 1000, 100, 0.001)
e0 = g.equity(100); g.step(90, 110); e1 = g.equity(100)
assert abs(e0 - 999.5) < 1e-9 and abs(e1 - 1049.107236842105) < 1e-9
r = run_on(WICKS + [(100, 110, 90, 100)], "R1", 4, "K1", wstart="2020-09-01 12:00")
assert r["final_equity"] == 1049.11
print(f"G-N1  CONFIRMED  class: equity {e0:.2f} -> {e1:.2f} on the creating candle; run(): one candle that opens and "
      f"closes at 100 ends at {r['final_equity']} on 1000")
r = run_on(WICKS + flat(SEP - 12) + [(100, 130, 100, 100)] + flat(5), "R1", 4, "K1")
assert r["final_equity"] == 1147.78 and r["restarts"] == 2
print(f"G-N1  CONFIRMED  recentre path: flat market, one 130 wick on the recentre candle (open 100, close 100): "
      f"final {r['final_equity']} on 1000")

# ---- G-N2 --------------------------------------------------------------------------------------------------------
for price, cash in ((80, -1.0), (90, -1.0), (94.9, 249.25), (100, 499.5)):
    assert abs(G.Grid(90, 110, 4, 1000, price, 0.001).cash - cash) < 1e-9
g = G.Grid(90, 110, 40, 3000, 80, 0.001)
print(f"G-N2  CONFIRMED  price at or below the lower bound: cash -1.00 on 1000 (N=4); {g.cash:.2f} on 3000 (N=40). "
      f"Always -fee x capital, about 0.1%")

# ---- G-N3 --------------------------------------------------------------------------------------------------------
c = kl(flat(50) + [(100, 130, 70, 100)])
closes = [k["c"] for k in c]
assert G.range_for("R1", c, 50, closes) == (70, 130) and G.range_for("R1", c, 49, closes) == (100.0, 100.0)
print("G-N3  CONFIRMED  range_for(i) includes candle i's own high and low: (70, 130) against (100, 100) one bar earlier")

# ---- G-N4 --------------------------------------------------------------------------------------------------------
r = run_on(WICKS + flat(2) + [(100, 100, 60, 100)] + flat(3), "R3", 4, "K1")
g = G.Grid(90, 110, 4, 1000, 100, 0.001); g.step(60, 100)
assert r["max_drawdown_pct"] < 0.1 and g.equity(60) < 850
print(f"G-N4  CONFIRMED  wick to 60, close back at 100: reported max drawdown {r['max_drawdown_pct']}%; the same book "
      f"marked at 60 is {g.equity(60):.2f} ({(g.equity(60) / 999.5 - 1) * 100:.1f}%)")

# ---- G-N5 --------------------------------------------------------------------------------------------------------
base = WICKS + flat(SEP - 13)
r_oct = run_on(base + [(100, 100, 95, 95), (95, 95, 78, 78)] + flat(48, 78), "R1", 4, "K2")     # breach 1 Oct 00:00
r_sep = run_on(base + [(100, 100, 78, 78)] + flat(48, 78), "R1", 4, "K2")                        # breach 30 Sep 23:00
assert r_oct["restarts"] == 2 and r_sep["restarts"] == 1
print(f"G-N5  CONFIRMED  close at 78 (stop level 81) on the first hour of October: recentred instead of stopped "
      f"(restarts {r_oct['restarts']}, final {r_oct['final_equity']}); the same close one hour earlier stops "
      f"(restarts {r_sep['restarts']}, final {r_sep['final_equity']})")

# ---- G-N6 / G-N7 -------------------------------------------------------------------------------------------------
assert r_sep["realized_grid_profit"] == 0.0 and r_sep["fees"] == 0.5 and r_sep["inventory_mtm_at_end"] == -110.39
print(f"G-N6  CONFIRMED  after the stop the account is all cash ({r_sep['final_equity']}), yet the report says realized "
      f"{r_sep['realized_grid_profit']} and inventory_mtm_at_end {r_sep['inventory_mtm_at_end']}")
print(f"G-N7  CONFIRMED  fees paid: 0.50 at creation + 0.39 on the liquidation of 5 coins at 78 = 0.89; reported {r_sep['fees']}")

# ---- G-N8 --------------------------------------------------------------------------------------------------------
n = 200 * 24
rows = flat(n - 2) + [(100, 110, 100, 100), (100, 100, 90, 100)] + flat(24) + [(100, 100, 78, 78)] + flat(24 * 20, 78)
rows += [(78, 120, 78, 120)] + flat(24 * 5 + 5, 120) + [(120, 140, 120, 120)] + flat(24 * 30, 120)
cur, log = {}, []
def _rf(rule, k_, i, closes_):
    cur["t"] = k_[i]["t"]; return REAL_RANGE(rule, k_, i, closes_)
class _LogGrid(REAL_GRID):
    def __init__(self, *a):
        log.append(datetime.fromtimestamp(cur["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H")); super().__init__(*a)
G.range_for, G.Grid = _rf, _LogGrid
run_on(rows, "R1", 4, "K2", wstart="2020-07-19", t0=1_577_836_800_000)
G.range_for, G.Grid = REAL_RANGE, REAL_GRID
assert log == ["2020-07-19 00", "2020-08-14 00", "2020-08-15 00"], log
print(f"G-N8  CONFIRMED  grids created at {log}: re-entry on 14 August, then a 'monthly' recentre on 15 August")

# ---- G-N9 --------------------------------------------------------------------------------------------------------
g = G.Grid(90, 110, 4, 1000, 106, 0.0); g.step(101, 111); g.step(99, 104)
h = G.Grid(90, 110, 4, 1000, 106, 0.0); h.step(101, 109.9); h.step(99, 104)
assert 2 not in g.lots and 2 in h.lots
print("G-N9  CONFIRMED  after a candle whose high reaches the top, the next downward cross of 100 is not bought; "
      "with a high of 109.9 it is. Direction: missed fills")

# ---- G-N10 -------------------------------------------------------------------------------------------------------
g = G.Grid(90, 110, 4, 1000, 100, 0.0); g.step(80, 100); r0 = g.realized; g.step(70, 96)
assert g.realized > r0
print("G-N10 CONFIRMED  a candle that closes below the range still fills resting orders; the plan says 'pauses'")

# ---- known four ---------------------------------------------------------------------------------------------------
g = G.Grid(90, 110, 4, 1000, 100, 0.001); cap = g.equity(100); g.liquidate(100)
assert abs((cap - g.cash) - 0.5) < 1e-9
print(f"G-K1  CONFIRMED  run() funds the new grid with equity before liquidation ({cap:.2f}); the cash after the sale "
      f"is {g.cash:.2f}. The 0.50 sale fee is never charged")
r = run_on(WICKS + flat(8) + [(100, 105.5, 94.5, 100)] + flat(SEP - 21) + flat(30), "R1", 4, "K1")
g = G.Grid(90, 110, 4, 1000, 100, 0.001); g.step(94.5, 105.5); g.step(100, 100)
assert r["restarts"] == 1 and abs(r["realized_grid_profit"] - 2 * g.realized) < 0.02 and abs(r["fees"] - 2 * g.fees) < 0.02
print(f"G-K2  CONFIRMED  one month boundary, no restart: reported realized {r['realized_grid_profit']} and fees {r['fees']}; "
      f"the grid's own books say {g.realized:.2f} and {g.fees:.2f}. Fees are doubled as well as realized")
import inspect
assert 'elif brk == "K3" and rule != "R2"' in inspect.getsource(G.run)
print("G-K3  CONFIRMED  line 171: K3 is skipped when the range rule is R2")
g = G.Grid(90, 110, 4, 1000, 102, 0.0); g.step(94.9, 100.1)
assert g.realized > 0
print(f"G-K4  CONFIRMED  candle low 94.9 high 100.1: buys 95 and sells 100 in the same hour ({g.realized:.2f}) whatever "
      f"the real order was")
try:
    run_on(flat(50), "R1", 4, "K1", wstart="2020-09-01 01:00"); raise SystemExit("expected a crash")
except ZeroDivisionError:
    print("EXTRA CONFIRMED  a flat lookback (high == low) raises ZeroDivisionError in Grid._idx")
print("All version 1 findings reproduced.")
