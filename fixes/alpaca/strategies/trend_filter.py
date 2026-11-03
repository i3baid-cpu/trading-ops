# trend_filter.py: hold SPY and QQQ while the last COMPLETED daily close is above the 200-day SMA, flat otherwise.
# PAPER ONLY. Fractional shares (floored to 3 decimals, min $1 notional), DAY market orders, no bracket orders.
# Replaces sma_cross.py (kept unchanged).
# Sizing uses capital_usd + realized P&L and P&L is reported vs capital_usd, not the account equity, so the bot can run
# a $1,000 book inside a larger paper account. Assumes no other SPY/QQQ positions in the account.
# Telegram (live only): startup, each FILL, each rejected/errored order, and one daily P&L + signal summary.
# Journal (live only): one JSON line per fill, order error, monthly check decision and daily sleeve value in
# strategies/trend_filter_journal.jsonl, read by the dashboard. The last check month in it survives restarts, so a
# restart mid-month no longer reruns the monthly check. Trading rule unchanged.
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from lumibot.strategies import Strategy

from strategies.notify import tg

TG_PREFIX = "[Alpaca paper]"
QTY_STEP = Decimal("0.001")
MIN_ORDER_USD = 1.0
BUDGET_FRACTION = 0.98  # size against 98% of the budget share so a fill above last price never exceeds the sleeve
STATE_FILE = "strategies/trend_filter_state.json"  # live only; ./strategies is bind-mounted, so it survives rebuilds
JOURNAL_FILE = "strategies/trend_filter_journal.jsonl"  # live only, append only


class TrendFilter(Strategy):
    def initialize(self, cfg):
        self.cfg = cfg
        self.p = cfg["params"]
        self.capital = float(cfg["capital_usd"])
        self.sleeptime = cfg.get("sleeptime", "1D")
        self.set_market("NYSE")
        self.reconciled = False
        self.last_summary_day = None
        # Sleeve ledger: per-symbol qty and cost basis from our own fills, plus realized P&L.
        self.book, problem = self._load_book()
        self.last_check_month = self._journal_last_check_month()
        self._journal("start", problem=problem, last_check_month=self.last_check_month)
        if problem:
            self.log_message(f"WARNING: {problem}; starting with no state, the first trading iteration "
                             f"reconciles the ledger from broker positions", color="red")
            self._notify(f"TrendFilter started. WARNING: {problem}; ledger will reconcile from broker positions")
        else:
            self._notify("TrendFilter started")

    def _load_book(self):
        # An empty, missing or invalid state file is treated as no state: start from an empty ledger and let
        # _reconcile() seed it from broker positions, as on a fresh start. Returns (book, problem or None).
        empty = {"realized": 0.0, "pos": {}}
        if self.is_backtesting:
            return empty, None
        if not os.path.exists(STATE_FILE):
            return empty, f"{STATE_FILE} missing"
        try:
            if os.path.getsize(STATE_FILE) == 0:
                raise ValueError("file is empty")
            with open(STATE_FILE) as f:
                raw = json.load(f)
            pos = {sym: {"qty": float(p["qty"]), "cost": float(p["cost"])} for sym, p in raw["pos"].items()}
            book = {"realized": float(raw["realized"]), "pos": pos}
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            # Keep the bad file for inspection; _reconcile() writes a fresh one.
            try:
                os.replace(STATE_FILE, STATE_FILE + ".invalid")
            except OSError:
                pass
            return empty, f"{STATE_FILE} invalid ({type(e).__name__}: {e}), kept as {STATE_FILE}.invalid"
        self.log_message(f"Loaded sleeve state from {STATE_FILE}: {book}")
        return book, None

    def _journal(self, event, **fields):
        # Append one event for the dashboard. A failed write is logged and never stops the bot.
        if self.is_backtesting:
            return
        try:
            row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
            with open(JOURNAL_FILE, "a") as f:
                f.write(json.dumps(row, default=float) + "\n")
        except Exception as e:
            self.log_message(f"WARNING: journal write failed ({type(e).__name__}: {e})", color="red")

    def _journal_last_check_month(self):
        # Month of the last monthly check in the journal, so a restart does not rerun it. None if unknown.
        if self.is_backtesting or not os.path.exists(JOURNAL_FILE):
            return None
        last = None
        try:
            with open(JOURNAL_FILE) as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("event") == "check" and isinstance(row.get("month"), str):
                        last = max(last or "", row["month"])
        except OSError as e:
            self.log_message(f"WARNING: journal not readable ({e}); the monthly check may run again this month", color="red")
        return last

    def _notify(self, text):
        if self.is_backtesting:
            return
        tg(f"{TG_PREFIX} {text}")

    def _save_book(self):
        if self.is_backtesting:
            return
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.book, f, indent=2)
        os.replace(tmp, STATE_FILE)

    def _record_fill(self, order, price, quantity):
        sym = order.asset.symbol
        q, px = float(quantity), float(price)
        p = self.book["pos"].setdefault(sym, {"qty": 0.0, "cost": 0.0})
        fill_pnl = 0.0
        if str(order.side).lower().startswith("buy"):
            p["qty"] += q
            p["cost"] += q * px
        else:
            avg = p["cost"] / p["qty"] if p["qty"] > 0 else px
            fill_pnl = (px - avg) * q
            self.book["realized"] += fill_pnl
            p["cost"] -= avg * q
            p["qty"] -= q
            if p["qty"] <= 1e-9:
                p["qty"], p["cost"] = 0.0, 0.0
        self._save_book()
        self._journal("fill", symbol=sym, side=str(order.side).lower(), qty=q, price=px, pnl=fill_pnl,
                      realized=self.book["realized"], order_id=str(getattr(order, "identifier", "")))
        msg = f"FILL {order.side} {q} {sym} @ {px:.2f}  realized P&L {self.book['realized']:+.2f}"
        self.log_message(msg)
        self._notify(msg)

    # Alpaca reports per-execution qty, so partial fills and the final fill are each booked once.
    def on_partially_filled_order(self, position, order, price, quantity, multiplier):
        self._record_fill(order, price, quantity)

    def on_filled_order(self, position, order, price, quantity, multiplier):
        self._record_fill(order, price, quantity)

    # Alpaca "rejected" maps to Lumibot's "error" status, which is dispatched here.
    def on_error_order(self, order, error=None):
        msg = f"ORDER ERROR {order.side} {order.quantity} {order.asset.symbol}: {error or getattr(order, 'error_message', '')}"
        self.log_message(msg, color="red")
        self._notify(msg)
        self._journal("order_error", symbol=order.asset.symbol, side=str(order.side).lower(), qty=order.quantity,
                      error=str(error or getattr(order, "error_message", "")))

    def _submit(self, sym, qty, side):
        # Alpaca only accepts fractional orders as DAY; Strategy.create_order defaults to GTC.
        # A failed submit raises from the broker; notify, then re-raise so Lumibot handles it as before.
        try:
            order = self.submit_order(self.create_order(sym, qty, side, time_in_force="day"))
        except Exception as e:
            self._notify(f"ORDER FAILED {side} {qty} {sym}: {e}")
            self._journal("order_error", symbol=sym, side=side, qty=qty, error=str(e))
            raise
        if order is None or str(order.status).lower() == "error":
            reason = getattr(order, "error_message", None) if order is not None else "submit_order returned None"
            self._notify(f"ORDER FAILED {side} {qty} {sym}: {reason}")
            self._journal("order_error", symbol=sym, side=side, qty=qty, error=str(reason))
        return order

    def _reconcile(self):
        # Align the ledger with broker positions after a restart or a lost state file.
        for sym in self.cfg["symbols"]:
            pos = self.get_position(sym)
            held = float(pos.quantity) if pos is not None else 0.0
            p = self.book["pos"].setdefault(sym, {"qty": 0.0, "cost": 0.0})
            if abs(held - p["qty"]) > 1e-6:
                avg = float(pos.avg_fill_price) if held and pos.avg_fill_price else 0.0
                self.log_message(f"{sym}: ledger qty {p['qty']} != broker qty {held}; reseeding at avg {avg:.2f}")
                p["qty"], p["cost"] = held, held * avg
        self._save_book()
        self.log_message("Reconciled ledger with broker: " +
                         ", ".join(f"{s} qty {self.book['pos'][s]['qty']}" for s in self.cfg["symbols"]))

    def _log_pnl(self):
        unreal = 0.0
        for sym, p in self.book["pos"].items():
            if p["qty"] > 0:
                unreal += p["qty"] * self.get_last_price(sym) - p["cost"]
        equity = self.capital + self.book["realized"] + unreal
        pnl = equity - self.capital
        line = (f"P&L vs ${self.capital:,.0f} base: sleeve value {equity:,.2f}  P&L {pnl:+,.2f} "
                f"({pnl / self.capital:+.2%})  realized {self.book['realized']:+,.2f}  unrealized {unreal:+,.2f}")
        self.log_message(line)
        return line, {"value": equity, "pnl": pnl, "realized": self.book["realized"], "unrealized": unreal}

    def _completed_closes(self, sym, n):
        bars = self.get_historical_prices(sym, n + 2, "day")
        if bars is None or bars.df.empty:
            return None
        df = bars.df
        # Drop today's bar only if it is actually dated today (live partial bar). Strategy has no
        # is_market_open() in lumibot 4.6.x, and in backtests the last bar is already yesterday's close.
        if len(df) > 1 and df.index[-1].date() >= self.get_datetime().date():
            df = df.iloc[:-1]
        return df["close"].tail(n + 1)

    def on_trading_iteration(self):
        if not self.reconciled:
            self._reconcile()
            self.reconciled = True
        pnl_line, pnl = self._log_pnl()
        lookback = self.p["sma"]
        # Signals for every symbol, computed daily so the summary can show them even on non-check days.
        signals = {}
        for sym in self.cfg["symbols"]:
            closes = self._completed_closes(sym, lookback)
            pos = self.get_position(sym)
            qty_held = Decimal(str(pos.quantity)) if pos is not None else Decimal(0)
            if closes is None or len(closes) < lookback:
                signals[sym] = (qty_held, None, None)
            else:
                signals[sym] = (qty_held, closes.iloc[-1], closes.tail(lookback).mean())
        day = self.get_datetime().date()
        if day != self.last_summary_day:
            self.last_summary_day = day
            rows = []
            for sym, (qty_held, last, sma) in signals.items():
                state = "in" if qty_held else "flat"
                if sma is None:
                    rows.append(f"{sym}: {state}, not enough history")
                else:
                    rows.append(f"{sym}: {state}, close {last:.2f} vs SMA{lookback} {sma:.2f} ({last / sma - 1:+.2%})")
            self._notify(f"{day} daily summary\n{pnl_line}\n" + "\n".join(rows))
            self._journal("daily", day=str(day), **pnl,
                          signals={s: {"qty": q, "close": c, "sma": m} for s, (q, c, m) in signals.items()})
        # check="monthly": evaluate only on the first iteration of each calendar month.
        if self.p.get("check", "daily") == "monthly":
            month = self.get_datetime().strftime("%Y-%m")
            if month == self.last_check_month:
                return
            self.last_check_month = month
        else:
            month = self.get_datetime().strftime("%Y-%m-%d")
        target_w = self.cfg["stake_pct"]
        band = self.p.get("band_pct", 0.0)
        for sym, (qty_held, last, sma) in signals.items():
            check = {"month": month, "symbol": sym, "qty_held": qty_held, "close": last, "sma": sma, "band": band}
            if sma is None:
                self.log_message(f"{sym}: not enough history, skipping")
                self._journal("check", **check, action="skip", reason="not enough price history")
                continue
            above = last > sma * (1 + band)
            below = last < sma * (1 - band)
            if above and qty_held == 0:
                # Sleeve compounds on realized P&L only: (capital_usd + realized) x stake_pct x 0.98, never above cash.
                sizing_base = self.capital + self.book["realized"]
                budget = max(0.0, min(self.get_cash(), sizing_base * target_w * BUDGET_FRACTION))
                price = self.get_last_price(sym)
                qty = (Decimal(str(budget)) / Decimal(str(price))).quantize(QTY_STEP, rounding=ROUND_DOWN)
                if qty > 0 and float(qty) * price >= MIN_ORDER_USD:
                    self._journal("check", **check, action="buy", qty=qty, price_est=price, budget=budget,
                                  reason=f"close above SMA{lookback} by more than the {band:.0%} band and not held")
                    self._submit(sym, qty, "buy")
                    self.log_message(f"BUY {qty} {sym} @ ~{price:.2f}  budget {budget:.2f} (base {sizing_base:,.2f})  "
                                     f"close {last:.2f} > SMA{lookback} {sma:.2f}")
                else:
                    self.log_message(f"{sym}: signal on but budget {budget:.2f} buys {qty} shares (< ${MIN_ORDER_USD:.0f})")
                    self._journal("check", **check, action="none", budget=budget,
                                  reason=f"signal on but the budget buys less than ${MIN_ORDER_USD:.0f}")
            elif below and qty_held > 0:
                self._journal("check", **check, action="sell", qty=qty_held,
                              reason=f"close below SMA{lookback} by more than the {band:.0%} band while held")
                self._submit(sym, qty_held, "sell")
                self.log_message(f"SELL {qty_held} {sym}  close {last:.2f} < SMA{lookback} {sma:.2f}")
            else:
                self.log_message(f"{sym}: hold ({'in' if qty_held else 'flat'}), close {last:.2f} vs SMA {sma:.2f}")
                why = ("already held and not below the band" if qty_held else "not held and not above the band")
                self._journal("check", **check, action="hold", reason=why)
