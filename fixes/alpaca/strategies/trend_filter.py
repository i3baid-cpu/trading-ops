# trend_filter.py: proposed replacement for sma_cross.py (Oct 30 2026 audit). PAPER ONLY.
#
# Rule: hold SPY and QQQ while the last COMPLETED daily close is above the 200-day SMA, be flat otherwise.
# Checked once per day after the close. Whole shares, market orders, no bracket orders.
#
# Why this instead of SMA 20/50 with 5%/10% brackets:
#   * the brackets guaranteed early exits from every trend (backtest +2% vs SPY +123%);
#   * 3 x 5% stake could never exceed 15% exposure, so it could not keep up with SPY by construction;
#   * Alpaca rejects bracket orders on fractional quantities, a likely reason the bot never traded;
#   * a long term trend filter does not promise to beat SPY; its documented value is a smaller drawdown
#     (it sidesteps part of 2008 and 2022 style declines) with roughly index like returns.
#
# Fixes versus sma_cross.py: open position count refreshed after each order, sizing from cash not portfolio
# value, completed bars only (no intraday repaint), whole share quantities, no sell_all() side effects.
from lumibot.strategies import Strategy


class TrendFilter(Strategy):
    def initialize(self, cfg):
        self.cfg = cfg
        self.p = cfg["params"]
        self.sleeptime = cfg.get("sleeptime", "1D")
        self.set_market("NYSE")

    def _completed_closes(self, sym, n):
        bars = self.get_historical_prices(sym, n + 2, "day")
        if bars is None or bars.df.empty:
            return None
        df = bars.df
        # Drop today's bar if the market is still open so the signal only uses completed sessions.
        if self.is_market_open() and len(df) > 1:
            df = df.iloc[:-1]
        return df["close"].tail(n + 1)

    def on_trading_iteration(self):
        symbols = self.cfg["symbols"]
        target_w = self.cfg["stake_pct"]                 # e.g. 0.5 each for SPY and QQQ
        lookback = self.p["sma"]                         # 200
        band = self.p.get("band_pct", 0.0)               # optional hysteresis, e.g. 0.01

        for sym in symbols:
            closes = self._completed_closes(sym, lookback)
            if closes is None or len(closes) < lookback:
                self.log_message(f"{sym}: not enough history, skipping")
                continue
            sma = closes.tail(lookback).mean()
            last = closes.iloc[-1]
            pos = self.get_position(sym)
            qty_held = int(pos.quantity) if pos is not None else 0

            above = last > sma * (1 + band)
            below = last < sma * (1 - band)

            if above and qty_held == 0:
                cash = self.get_cash()
                budget = min(cash, self.get_portfolio_value() * target_w)
                price = self.get_last_price(sym)
                qty = int(budget // price)
                if qty >= 1:
                    self.submit_order(self.create_order(sym, qty, "buy"))
                    self.log_message(f"BUY {qty} {sym} @ ~{price:.2f}  close {last:.2f} > SMA{lookback} {sma:.2f}")
                else:
                    self.log_message(f"{sym}: signal on but budget {budget:.2f} buys 0 shares")
            elif below and qty_held > 0:
                self.submit_order(self.create_order(sym, qty_held, "sell"))
                self.log_message(f"SELL {qty_held} {sym}  close {last:.2f} < SMA{lookback} {sma:.2f}")
            else:
                self.log_message(f"{sym}: hold ({'in' if qty_held else 'flat'}), close {last:.2f} vs SMA {sma:.2f}")
