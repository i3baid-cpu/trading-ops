# MemeSleeveV3 gate check

Generated 2026-11-01 10:10 UTC. Completed candles only.

## BTC daily gate

| Daily candle | Close | EMA100 | Close vs EMA100 | Gate |
|---|---|---|---|---|
| 2026-10-31 | 77582.02 | 77808.14 | -0.29% | **SHUT** |

BTC 1d history used: 1400 candles from 2023-01-01.

## Pairs, last completed 4h candle

| Pair | Candle (UTC open) | Close | EMA50 | Prior 20 bar high | Close>EMA50 | Close>HH20 | Entry fired in last 3 |
|---|---|---|---|---|---|---|---|
| DOGE/USDT | 2026-11-01 04:00 | 0.07583 | 0.07748165452 | 0.08148 | no | no | no |
| PEPE/USDT | 2026-11-01 04:00 | 5.01e-06 | 4.789742995e-06 | 5.68e-06 | yes | no | no |
| SHIB/USDT | 2026-11-01 04:00 | 4.69e-06 | 4.846350162e-06 | 5.1e-06 | no | no | no |
| FLOKI/USDT | 2026-11-01 04:00 | 2.353e-05 | 2.35767403e-05 | 2.515e-05 | no | no | no |

## Entry conditions on the last three 4h candles

### DOGE/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-10-31 20:00 | 0.07563 | 0.07763188813 | 0.08148 | no | shut | no | no | **no** |
| 2026-11-01 00:00 | 0.07552 | 0.07754906899 | 0.08148 | no | shut | no | no | **no** |
| 2026-11-01 04:00 | 0.07583 | 0.07748165452 | 0.08148 | no | shut | no | no | **no** |

### PEPE/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-10-31 20:00 | 5e-06 | 4.769763236e-06 | 5.68e-06 | no | shut | yes | no | **no** |
| 2026-11-01 00:00 | 5.05e-06 | 4.780752913e-06 | 5.68e-06 | no | shut | yes | no | **no** |
| 2026-11-01 04:00 | 5.01e-06 | 4.789742995e-06 | 5.68e-06 | no | shut | yes | no | **no** |

### SHIB/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-10-31 20:00 | 4.67e-06 | 4.859782079e-06 | 5.1e-06 | no | shut | no | no | **no** |
| 2026-11-01 00:00 | 4.68e-06 | 4.852731802e-06 | 5.1e-06 | no | shut | no | no | **no** |
| 2026-11-01 04:00 | 4.69e-06 | 4.846350162e-06 | 5.1e-06 | no | shut | no | no | **no** |

### FLOKI/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-10-31 20:00 | 2.323e-05 | 2.359206228e-05 | 2.515e-05 | no | shut | no | no | **no** |
| 2026-11-01 00:00 | 2.325e-05 | 2.357864807e-05 | 2.515e-05 | no | shut | no | no | **no** |
| 2026-11-01 04:00 | 2.353e-05 | 2.35767403e-05 | 2.515e-05 | no | shut | no | no | **no** |

## Dry run: open trades

_None._

## Dry run: last 5 closed trades

|   id | pair       | strategy     | enter_tag   | open_date                  |   open_rate |   stake_amount |        amount |   stop_loss | close_date                 |   close_rate | close_profit   |   close_profit_abs | exit_reason   |
|-----:|:-----------|:-------------|:------------|:---------------------------|------------:|---------------:|--------------:|------------:|:---------------------------|-------------:|:---------------|-------------------:|:--------------|
|   25 | DOGE/USDT  | MemeSleeveV1 |             | 2026-10-30 20:00:01.915515 |   0.07541   |        24.9607 | 331           |    0.0641   | 2026-10-30 21:27:19.695000 |    0.07546   | -0.13%         |        -0.033388   | trend_lost_4h |
|   24 | SHIB/USDT  | MemeSleeveV1 |             | 2026-10-30 19:50:07.355779 |   4.74e-06  |        25      |   5.27426e+06 |    4.03e-06 | 2026-10-30 21:27:04.702000 |    4.75e-06  | 0.01%          |         0.00268987 | trend_lost_4h |
|   23 | PEPE/USDT  | MemeSleeveV1 |             | 2026-10-30 17:35:01.898430 |   5.23e-06  |        25      |   4.78011e+06 |    4.71e-06 | 2026-10-30 18:05:02.913000 |    5.12e-06  | -2.3%          |        -0.575287   | exit_signal   |
|   22 | FLOKI/USDT | MemeSleeveV1 |             | 2026-10-30 15:35:07.099029 |   2.422e-05 |        25      |   1.0322e+06  |    2.18e-05 | 2026-10-30 17:48:21.305000 |    2.405e-05 | -0.9%          |        -0.225299   | exit_signal   |
|   20 | DOGE/USDT  | MemeSleeveV1 |             | 2026-10-30 15:05:01.776708 |   0.07605   |        24.9444 | 328           |    0.06845  | 2026-10-30 16:50:11.289000 |    0.07553   | -0.88%         |        -0.220278   | exit_signal   |


## Provenance

Copied from `~/trading_fixes/results/v3_gate_check.md` on the VPS (generated 2026-11-01 10:10 UTC).
Data range: BTC/USDT 1d from 2023-01-01 to the 2026-10-31 close (1400 candles); DOGE, PEPE, SHIB, FLOKI /USDT 4h
up to the 2026-11-01 04:00 candle; Binance spot. Dry run trades from `tradesv3.dryrun.sqlite`.
Command: not recorded; the one-off script that produced this file was not saved.
