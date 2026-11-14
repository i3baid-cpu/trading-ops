"""Accounting tests for scripts/grid_backtest.py on synthetic hourly candles (no network). Run: python3 scripts/tests/test_grid.py"""
import math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import grid_backtest as G


def candles(prices):
    out = []
    for i, p in enumerate(prices):
        prev = prices[i - 1] if i else p
        out.append({"t": 1_600_000_000_000 + i * 3_600_000, "o": prev, "h": max(prev, p) * 1.0005, "l": min(prev, p) * 0.9995, "c": p, "v": 1.0})
    return out


def test_equity_identity_and_sideways_profit():
    # price oscillates 90..110 around 100 for 400 hours: a grid must realise profit and end near flat inventory
    prices = [100 + 10 * math.sin(i / 8) for i in range(400)]
    g = G.Grid(85, 115, 20, 3000, prices[0], 0.001)
    for k in candles(prices):
        g.step(k["l"], k["h"])
        assert abs(g.equity(k["c"]) - (g.cash + g.inventory() * k["c"])) < 1e-6
    assert g.realized > 0, g.realized
    assert g.fees > 0
    print(f"[OK] sideways: realized {g.realized:.2f}, fees {g.fees:.2f}, equity {g.equity(prices[-1]):.2f} on 3000")


def test_crash_shows_inventory_loss():
    prices = [100 - i * 0.2 for i in range(300)]  # 100 -> 40, straight down
    g = G.Grid(85, 115, 20, 3000, prices[0], 0.001)
    for k in candles(prices):
        g.step(k["l"], k["h"])
    eq = g.equity(prices[-1])
    assert eq < 3000 * 0.75, eq            # the grid is left holding coins bought all the way down
    assert g.realized <= 1e-9              # nothing sold on the way down
    print(f"[OK] crash: equity {eq:.2f} on 3000, realized {g.realized:.2f}, inventory {g.inventory():.3f} coins")


def test_rally_caps_upside():
    prices = [100 + i * 0.2 for i in range(300)]  # 100 -> 160
    g = G.Grid(85, 115, 20, 3000, prices[0], 0.001)
    for k in candles(prices):
        g.step(k["l"], k["h"])
    eq = g.equity(prices[-1])
    hold = 3000 * prices[-1] / prices[0]
    assert g.inventory() < 1e-9            # everything sold on the way up
    assert eq < hold                       # and the grid trails buy and hold
    print(f"[OK] rally: equity {eq:.2f} vs hold {hold:.2f}")


def test_no_lot_sold_twice_or_bought_twice():
    prices = [100, 95, 100, 95, 100, 95, 100]
    g = G.Grid(90, 110, 4, 1000, 100, 0.0)  # levels 90,95,100,105,110
    for k in candles(prices):
        g.step(k["l"], k["h"])
    assert all(v >= 0 for v in g.lots.values()) and g.cash >= -1e-6
    print("[OK] lot bookkeeping")


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
    print("All grid tests passed.")
