# MemeSleeveV4d: research candidate 5 of docs/RESEARCH_CYCLE_2026-11.md. MemeSleeveV4 with one change: a two stage
# exit. Half the position is sold once the trade is up 10%; the rest runs with V4's trailing stop and exit signal.
# The plan names custom_exit, but custom_exit can only close a whole trade, so the half exit uses Freqtrade's
# partial exit (adjust_trade_position returning a negative stake). Research only.
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair


class MemeSleeveV4d(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = False
    minimal_roi = {"0": 1.0}
    stoploss = -0.15
    trailing_stop = True
    trailing_stop_positive = 0.10
    trailing_stop_positive_offset = 0.20
    trailing_only_offset_is_reached = True
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count = 700
    position_adjustment_enable = True
    max_entry_position_adjustment = 0
    order_types = {"entry": "limit", "exit": "limit", "stoploss": "market", "stoploss_on_exchange": False}

    @property
    def protections(self):
        return [{"method": "CooldownPeriod", "stop_duration_candles": 6}]

    def informative_pairs(self):
        return [("BTC/USDT", "1d")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["hh20"] = dataframe["high"].rolling(20).max().shift(1)
        dataframe["vol_mean"] = dataframe["volume"].rolling(20).mean()
        btc = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe="1d")
        btc["btc_ema100"] = ta.EMA(btc, timeperiod=100)
        btc["btc_up"] = (btc["close"] > btc["btc_ema100"]).astype(int)
        dataframe = merge_informative_pair(dataframe, btc[["date", "btc_up"]], self.timeframe, "1d", ffill=True)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["btc_up_1d"] == 1)
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["hh20"])
            & (dataframe["volume"] > dataframe["vol_mean"])
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "breakout_4h")
        return dataframe

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs):
        if trade.nr_of_successful_exits == 0 and current_profit >= 0.10:
            return -(trade.stake_amount / 2), "half_at_10pct"
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["ema50"]) | (dataframe["btc_up_1d"] == 0),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_lost_4h")
        return dataframe
