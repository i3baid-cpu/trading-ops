# MemeSleeveV3: slow trend following. Long only while the pair is above its 4h EMA50 and BTC is above its
# daily EMA100, entered on a 20 bar breakout, exited on a 4h close below EMA50 or the BTC filter turning off.
# Wide stop, wide trailing. Few trades a year per pair. Designed from the 36 month regime report, so the
# 2023-10 to 2025-10 window is in sample and 2025-10 to 2026-10 is the held out test.
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair


class MemeSleeveV3(IStrategy):
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

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["close"] < dataframe["ema50"]) | (dataframe["btc_up_1d"] == 0),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_lost_4h")
        return dataframe
