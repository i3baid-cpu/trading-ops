# MemeSleeveV2: proposed replacement for MemeSleeveV1 (Oct 30 2026 audit).
# Separate file. V1 is untouched. Run in DRY RUN only until the go-live gate in DEPLOY.md is met.
#
# What changed and why (each line maps to a V1 defect):
#   timeframe 5m -> 15m            V1 traded ~15 times a day; fees (0.2% round trip) ate the expectancy.
#   1h trend filter (pair + BTC)   V1 had no regime filter; the docstring promised a 24h momentum rule that was never coded.
#   exit on close < EMA21 (2 bars) V1 exited on any 5m EMA cross; 11 of 13 signal exits were ~-1% noise losses.
#   RSI > 80 exit removed          sold into strength, against the momentum thesis.
#   ROI table removed              V1 forced a sale at 0% after 120 min, capping reward at ~4% against a 10% stop.
#   trailing stop 2% / offset 4%   lets winners run, which is the only way a 40% win rate strategy can pay.
#   stoploss -6%                   tighter initial risk; the trailing stop takes over once +4% is reached.
#   protections                    cooldown after a stop, pause after 3 stops in 12 h, pause on 8% drawdown.
#   custom_stake_amount            never commits more than 25 USDT, and skips if free balance < 2 stakes (live safety).
from datetime import datetime
from typing import Optional

import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, merge_informative_pair


class MemeSleeveV2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    informative_timeframe = "1h"
    can_short = False

    # No time based ROI: a hard cap only, exits come from the trailing stop or the exit signal.
    minimal_roi = {"0": 0.15}

    stoploss = -0.06
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 220  # 1h EMA50 needs 50 x 4 = 200 15m candles

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,  # set True in LIVE config so the exchange holds the stop if the VPS dies
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 4},
            {"method": "StoplossGuard", "lookback_period_candles": 48, "trade_limit": 3, "stop_duration_candles": 24, "only_per_pair": False},
            {"method": "MaxDrawdown", "lookback_period_candles": 96, "trade_limit": 6, "stop_duration_candles": 48, "max_allowed_drawdown": 0.08},
        ]

    def informative_pairs(self):
        pairs = [(p, self.informative_timeframe) for p in self.dp.current_whitelist()]
        pairs.append(("BTC/USDT", self.informative_timeframe))
        return pairs

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 15m
        dataframe["ema9"] = ta.EMA(dataframe, timeperiod=9)
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["vol_mean"] = dataframe["volume"].rolling(20).mean()
        dataframe["atr_pct"] = ta.ATR(dataframe, timeperiod=14) / dataframe["close"]

        # 1h pair trend
        inf = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=self.informative_timeframe)
        inf["ema50"] = ta.EMA(inf, timeperiod=50)
        inf["trend_up"] = (inf["close"] > inf["ema50"]).astype(int)
        dataframe = merge_informative_pair(dataframe, inf[["date", "ema50", "trend_up"]], self.timeframe, self.informative_timeframe, ffill=True)

        # 1h BTC regime
        btc = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe=self.informative_timeframe)
        btc["btc_ema50"] = ta.EMA(btc, timeperiod=50)
        btc["btc_up"] = (btc["close"] > btc["btc_ema50"]).astype(int)
        dataframe = merge_informative_pair(dataframe, btc[["date", "btc_up"]], self.timeframe, self.informative_timeframe, ffill=True)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["trend_up_1h"] == 1)
            & (dataframe["btc_up_1h"] == 1)
            & (dataframe["ema9"] > dataframe["ema21"])
            & (dataframe["close"] > dataframe["ema21"])
            & (dataframe["rsi"] > 50)
            & (dataframe["rsi"] < 70)
            & (dataframe["volume"] > dataframe["vol_mean"])
            & (dataframe["atr_pct"] < 0.04)  # skip the most violent candles
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "trend_pullback_15m")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        below = dataframe["close"] < dataframe["ema21"]
        dataframe.loc[
            (below & below.shift(1).fillna(False))  # two consecutive 15m closes below EMA21
            | (dataframe["btc_up_1h"] == 0),        # BTC regime turned down: leave
            ["exit_long", "exit_tag"],
        ] = (1, "trend_lost")
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float, leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        # Hard ceiling of 25 USDT per trade and keep two stakes of free balance; otherwise skip the trade.
        stake = min(proposed_stake, 25.0)
        try:
            free = self.wallets.get_free(self.config["stake_currency"])
            if free < 2 * stake:
                return 0.0
        except Exception:
            pass
        return stake
