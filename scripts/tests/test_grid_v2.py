"""Tests for scripts/grid_backtest_v2.py (proposal). Synthetic hourly candles, no network.
Run: python3 scripts/tests/test_grid_v2.py
Each test names the audit finding it guards (docs/INDEPENDENT_AUDIT_FINDINGS_2026-11-14.md)."""
import os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import grid_backtest_v2 as V

H = 3_600_000
T0 = 1_598_918_400_000                      # 2020-09-01 00:00 UTC
SEP = 30 * 24                               # hours in September 2020


def kl(rows, t0=T0):
    return [{"t": t0 + i * H, "o": o, "h": h, "l": l, "c": c, "v": 1.0} for i, (o, h, l, c) in enumerate(rows)]


def flat(n, p=100.0):
    return [(p, p, p, p)] * n


def run_on(rows, rule, n, brk, wstart="2020-09-01 12:00", t0=T0, **kw):
    candles = kl(rows, t0)
    V.load_klines = lambda pair, start, end, interval="1h": candles
    kw.setdefault("capital", 1000); kw.setdefault("fee", 0.001)
    return V.run("SYN", rule, n, brk, kw.pop("capital"), kw.pop("fee"), "2020-01-01", "2030-01-01", wstart,
                 return_ledger=True, **kw)


WICKS = flat(10) + [(100, 110, 100, 100), (100, 100, 90, 100)]      # gives R1 and R3 a 90..110 range; 12 candles


def led():
    return V.Ledger(1000)


def test_n1_no_fill_on_the_candle_that_set_the_orders():
    # the decision candle (index 12) swings 90..110 and closes at 100; the grid starts at the NEXT open
    rows = WICKS + [(100, 110, 90, 100)] + flat(5)
    r = run_on(rows, "R1", 4, "K1", wstart="2020-09-01 13:00")
    L = r["_ledger"]
    assert r["grid_realized"] == 0 and r["fills"] == 1, r                      # only the starting inventory
    assert abs(r["final_equity_mtm"] - (1000 - L.fees)) < 0.01
    created = L.events[0][0]
    assert all(f[0] >= created for f in L.fills)
    print(f"[OK] G-N1: decision candle swing earns nothing; equity {r['final_equity_mtm']} = 1000 minus {L.fees:.2f} fees")


def test_n1_recentre_does_not_trade_its_own_candle():
    # flat September; the last September hour wicks to 130 and closes at 100, which widens the R1 range to 90..130.
    # The OLD grid (90..110) may trade that wick with the orders it already had. The NEW grid must not: version 1
    # sold the new grid's lots at 120 and 130 inside the candle that defined them and ended at 1147.78.
    rows = WICKS + flat(SEP - 13) + [(100, 130, 100, 100)] + flat(30)
    r = run_on(rows, "R1", 4, "K1")
    L = r["_ledger"]
    t_dec = T0 + (SEP - 1) * H
    assert r["events"]["recentre"] == 1 and L.events[1][0] == t_dec + H, L.events
    assert all(f[3] <= 110 + 1e-9 for f in L.fills if f[0] <= t_dec), L.fills       # only old grid levels on that candle
    assert not [f for f in L.fills if f[0] > t_dec and f[2] is not None]              # flat afterwards: no level fills
    assert r["final_equity_mtm"] < 1030, r["final_equity_mtm"]
    print(f"[OK] G-N1 on recentre: new range trades from the next open only; ends at {r['final_equity_mtm']} (version 1: 1147.78)")


def test_n2_cash_never_negative():
    for fee in (0.0, 0.001, 0.01):
        for price in (50, 80, 90, 94.9, 95, 100, 109.99, 110, 150):
            g = V.Grid(90, 110, 4, 1000, 0.0, price, fee, led(), 0)
            assert g.cash >= -1e-9, (fee, price, g.cash)
            for x in (60, 120, 85, 111, 90, 110):
                g.move(x, 1)
                assert g.cash >= -1e-9, (fee, price, x, g.cash)
    g = V.Grid(90, 110, 4, 1000, 0.0, 80, 0.001, led(), 0)
    assert len(g.lots) == 4 and g.cash >= -1e-9
    print(f"[OK] G-N2: price below the range buys 4 lots and leaves cash {abs(g.cash):.6f} (version 1: -1.0)")


def test_ledger_reconciles_on_random_walks():
    rnd = random.Random(7)
    for trial in range(40):
        p = 100.0; rows = list(WICKS)
        for _ in range(900):
            o = p; c = max(20.0, p * (1 + rnd.gauss(0, 0.012)))
            h = max(o, c) * (1 + abs(rnd.gauss(0, 0.004))); l = min(o, c) * (1 - abs(rnd.gauss(0, 0.004)))
            rows.append((o, h, l, c)); p = c
        rule, brk = rnd.choice([("R1", "K1"), ("R1", "K2"), ("R1", "K3"), ("R3", "K1")])
        for path in ("OLHC", "OHLC"):
            for rc in ("net", "gross"):
                r = run_on(rows, rule, rnd.choice([4, 10, 20]), brk, path=path, recentre=rc)   # run() asserts every candle
                assert r["reconciles"], r
                assert r["max_drawdown_intrabar_pct"] >= r["max_drawdown_close_pct"] - 1e-9
                assert r["final_equity_if_liquidated"] <= r["final_equity_mtm"] + 1e-9
    print("[OK] G-N6/N7/K2: equity = capital + grid profit + liquidation profit + open profit - fees on 160 random runs")


def test_k4_n9_path_order_matters_and_is_explicit():
    def one(path):
        L = led(); g = V.Grid(90, 110, 4, 1000, 0.0, 100.05, 0.0, L, 0)
        for x in ([100.05, 94.9, 100.1, 94.95] if path == "OLHC" else [100.05, 100.1, 94.9, 94.95]):
            g.move(x, 1)
        return L.grid_realized, g.inventory()
    a, b = one("OLHC"), one("OHLC")
    assert a[0] > 0 and b[0] == 0, (a, b)
    print(f"[OK] G-K4: same candle, low first realizes {a[0]:.2f}, high first realizes {b[0]:.2f}; both are reported")


def test_n9_rebuy_after_touching_the_top():
    L = led(); g = V.Grid(90, 110, 4, 1000, 0.0, 106, 0.0, L, 0)
    for x in (111, 101, 104, 99):
        g.move(x, 1)
    assert 2 in g.lots, g.lots                         # the 100 level is bought when price crosses it downward
    print("[OK] G-N9: level 100 is bought on the cross after a candle that touched the top (version 1 missed it)")


def test_n4_intrabar_drawdown_is_seen():
    rows = WICKS + flat(2) + [(100, 100, 60, 100)] + flat(3)
    r = run_on(rows, "R3", 4, "K1")
    assert r["max_drawdown_close_pct"] < 1 and r["max_drawdown_intrabar_pct"] > 15, r
    print(f"[OK] G-N4: wick to 60: drawdown on closes {r['max_drawdown_close_pct']}%, intrabar {r['max_drawdown_intrabar_pct']}%")


def test_n5_stop_has_priority_over_the_monthly_recentre():
    # last September hour closes 95 (inside); first October hour closes 78, below 90 * 0.9 = 81
    rows = WICKS + flat(SEP - 13) + [(100, 100, 95, 95), (95, 95, 78, 78)] + flat(48, 78)
    r = run_on(rows, "R1", 4, "K2")
    assert r["events"] == {"create": 1, "recentre": 0, "stop": 1}, r["events"]
    assert r["open_pnl_at_end"] == 0 and r["liquidation_pnl"] < 0 and r["reconciles"]
    # and a breach that closes on the very candle the monthly recentre is decided: the stop still wins
    rows = WICKS + flat(SEP - 13) + [(100, 100, 78, 78)] + flat(48, 78)
    r2 = run_on(rows, "R1", 4, "K2")
    assert r2["events"] == {"create": 1, "recentre": 0, "stop": 1}, r2["events"]
    print(f"[OK] G-N5/N6: stop fires in both orderings; loss booked as liquidation {r['liquidation_pnl']}, nothing left open")


def test_k1_recentre_fee_is_charged_net_and_gross():
    # recentre from 90..110 to 90..130 at an unchanged price of 100: 2 lots held, 3 lots wanted
    out = {}
    for mode in ("net", "gross"):
        L = led(); g = V.Grid(90, 110, 4, 1000, 0.0, 100, 0.001, L, 0, mode)
        e0, f0, held = g.equity(100), L.fees, g.inventory()
        coins = g.close_lots(100)
        g2 = V.Grid(90, 130, 4, g.cash - coins * 100, coins, 100, 0.001, L, 1, mode)
        traded = abs(g2.inventory() - held) if mode == "net" else g2.inventory() + held
        assert abs((e0 - g2.equity(100)) - traded * 100 * 0.001) < 1e-9          # equity falls by exactly the fee
        assert abs((L.fees - f0) - traded * 100 * 0.001) < 1e-9                  # and the fee total shows it
        assert abs(1000 + L.grid_realized + L.liquidation_pnl + g2.open_pnl(100) - L.fees - g2.equity(100)) < 1e-9
        out[mode] = L.fees - f0
    assert out["gross"] > out["net"] > 0
    print(f"[OK] G-K1: recentre fee on 1000 is {out['net']:.4f} net, {out['gross']:.4f} gross; charged and reported")


def test_k3_works_under_r2():
    n = 200 * 24
    rows = flat(n + 10) + [(100, 100, 100, 100), (100, 131, 100, 130)] + flat(5, 130)     # jumps above SMA * 1.2
    r = run_on(rows, "R2", 4, "K3", wstart="2020-01-01", t0=1_577_836_800_000)
    assert r["events"]["recentre"] >= 1, r["events"]
    r1 = run_on(rows, "R2", 4, "K1", wstart="2020-01-01", t0=1_577_836_800_000)
    assert r1["events"]["recentre"] == 0                                                   # R2 alone waits 24 hours
    print("[OK] G-K3: K3 recentres at once under R2; R2 with K1 waits for its 24 hours")


def n8_rows():
    """200 days flat at 100 from 1 Jan 2020, a stop on 20 July, price at 120 from 9 August (above the 200 day average),
    re-entry on 14 August, then a 140 wick six hours later that moves the R1 range by more than 2%."""
    n = 200 * 24                                         # 19 July 2020 00:00
    rows = flat(n - 2) + [(100, 110, 100, 100), (100, 100, 90, 100)] + flat(24) + [(100, 100, 78, 78)] + flat(24 * 20, 78)
    rows += [(78, 120, 78, 120)] + flat(24 * 5 + 5, 120) + [(120, 140, 120, 120)] + flat(24 * 30, 120)
    return rows


def test_n8_month_key_is_set_on_re_entry():
    r = run_on(n8_rows(), "R1", 4, "K2", wstart="2020-07-19", t0=1_577_836_800_000)
    ev = [(V.datetime.fromtimestamp(t / 1000, tz=V.timezone.utc).strftime("%Y-%m-%d %H"), kind) for t, kind, _ in r["_ledger"].events]
    assert [k for _, k in ev] == ["create", "stop", "create", "recentre"], ev
    assert ev[2][0].startswith("2020-08-14") and ev[3][0] == "2020-09-01 00", ev     # version 1 recentres on 15 August
    print(f"[OK] G-N8: re-entry {ev[2][0]}, next recentre {ev[3][0]} (first hour of the next month)")


def test_n10_k1_definition_resting_orders_fill():
    L = led(); g = V.Grid(90, 110, 4, 1000, 0.0, 100, 0.0, L, 0)
    for x in (100, 80, 96, 85):                           # closes below the range, wick back inside
        g.move(x, 1)
    assert L.grid_realized > 0
    print("[OK] G-N10: K1 keeps resting orders live; documented as the definition")


def test_degenerate_range_is_skipped_not_a_crash():
    r = run_on(flat(50), "R1", 4, "K1", wstart="2020-09-01 01:00")
    assert r["restarts"] == 0 and r["final_equity_mtm"] == 1000
    print("[OK] flat history (hi == lo) creates no grid; version 1 raises ZeroDivisionError")


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
    print("All version 2 grid tests passed.")
