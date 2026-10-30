# Backtest the trend filter against SPY, 2007 onward so the 2008, 2020 and 2022 declines are included.
# docker compose run --rm -v ./backtest_v2.py:/app/backtest_v2.py -v ./config_v2.json:/app/config.json -v ./logs:/app/logs lumibot python backtest_v2.py
import json
from datetime import datetime
from lumibot.backtesting import YahooDataBacktesting
from strategies.trend_filter import TrendFilter

cfg = json.load(open("config.json"))
for start, end, label in [
    (datetime(2007, 1, 1), datetime(2016, 12, 31), "train 2007-2016"),
    (datetime(2017, 1, 1), datetime(2026, 10, 1), "test 2017-2026"),
]:
    print(f"\n=== {label} ===")
    TrendFilter.backtest(
        YahooDataBacktesting, start, end,
        parameters={"cfg": cfg}, benchmark_asset="SPY", budget=10000,
        show_plot=False, show_tearsheet=False, save_tearsheet=True,
    )
# Read the two tearsheets. Accept the strategy only if, on the TEST window, CAGR is within 3 points of SPY
# and max drawdown is at least 30% smaller than SPY's. If it is not, do not "tune" the 200; change nothing and tell me.
