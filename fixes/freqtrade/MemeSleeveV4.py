# MemeSleeveV4: MemeSleeveV3's rules unchanged, run on DOGE PEPE SHIB FLOKI plus SOL /USDT with 3 open trades.
# Variant 5 of the SOL study (docs/RESEARCH_V4_PLAN.md, results/research_v4_sol.md): +79.4 USDT PF 1.64 on the
# unseen 2020-08 to 2023-10 window, +82.6 PF 1.38 on 2023-10 to 2026-10, robust to fee 0.2%, 15m detail and +-25%
# neighbours. Most of the gain is SOL; the third slot adds capital, not edge. The coin list and max_open_trades 3
# live in config.json; this file only gives the setup its own name so its trades are labelled V4.
import talib.abstract as ta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, merge_informative_pair


class MemeSleeveV4(IStrategy):
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
