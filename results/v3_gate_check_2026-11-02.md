# MemeSleeveV3 gate check

Generated 2026-11-02 14:08 UTC. Completed candles only.

## BTC daily gate

| Daily candle | Close | EMA100 | Close vs EMA100 | Gate |
|---|---|---|---|---|
| 2026-10-28 | 81343.50 | 77818.23 | +4.53% | **OPEN** |
| 2026-10-29 | 77991.89 | 77821.67 | +0.22% | **OPEN** |
| 2026-10-30 | 77368.77 | 77812.70 | -0.57% | **SHUT** |
| 2026-10-31 | 77582.02 | 77808.14 | -0.29% | **SHUT** |
| 2026-11-01 | 78354.00 | 77818.94 | +0.69% | **OPEN** |

BTC 1d history used: 1401 candles from 2023-01-01 to 2026-11-01.

## Pairs, last completed 4h candle

| Pair | Candle (UTC open) | Close | EMA50 | Prior 20 bar high | Close>EMA50 | Close>HH20 | Entry fired in last 3 |
|---|---|---|---|---|---|---|---|
| DOGE/USDT | 2026-11-02 08:00 | 0.07541 | 0.077008573 | 0.07682 | no | no | no |
| PEPE/USDT | 2026-11-02 08:00 | 4.85e-06 | 4.809466e-06 | 5.5e-06 | yes | no | no |
| SHIB/USDT | 2026-11-02 08:00 | 4.64e-06 | 4.8070801e-06 | 4.84e-06 | no | no | no |
| FLOKI/USDT | 2026-11-02 08:00 | 2.275e-05 | 2.3450058e-05 | 2.47e-05 | no | no | no |

## Entry conditions on the last three 4h candles

### DOGE/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 00:00 | 0.07619 | 0.077150304 | 0.08148 | no | open | no | no | **no** |
| 2026-11-02 04:00 | 0.0752 | 0.077073821 | 0.07933 | no | open | no | no | **no** |
| 2026-11-02 08:00 | 0.07541 | 0.077008573 | 0.07682 | no | open | no | no | **no** |

Last entry signal in the fetched window (2026-05-20 00:00 to 2026-11-02 08:00): 2026-10-28 00:00.

### PEPE/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 00:00 | 4.92e-06 | 4.8073141e-06 | 5.68e-06 | no | open | yes | no | **no** |
| 2026-11-02 04:00 | 4.82e-06 | 4.8078116e-06 | 5.5e-06 | no | open | yes | no | **no** |
| 2026-11-02 08:00 | 4.85e-06 | 4.809466e-06 | 5.5e-06 | no | open | yes | no | **no** |

Last entry signal in the fetched window (2026-05-20 00:00 to 2026-11-02 08:00): 2026-10-29 12:00.

### SHIB/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 00:00 | 4.72e-06 | 4.8205894e-06 | 5.1e-06 | no | open | no | no | **no** |
| 2026-11-02 04:00 | 4.65e-06 | 4.8138997e-06 | 4.94e-06 | no | open | no | no | **no** |
| 2026-11-02 08:00 | 4.64e-06 | 4.8070801e-06 | 4.84e-06 | no | open | no | no | **no** |

Last entry signal in the fetched window (2026-05-20 00:00 to 2026-11-02 08:00): 2026-10-28 08:00.

### FLOKI/USDT

| Candle (UTC open) | Close | EMA50 | HH20 | Vol > mean20 | BTC gate | Close>EMA50 | Close>HH20 | Entry |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02 00:00 | 2.323e-05 | 2.350878e-05 | 2.515e-05 | no | open | no | no | **no** |
| 2026-11-02 04:00 | 2.274e-05 | 2.3478631e-05 | 2.47e-05 | no | open | no | no | **no** |
| 2026-11-02 08:00 | 2.275e-05 | 2.3450058e-05 | 2.47e-05 | no | open | no | no | **no** |

Last entry signal in the fetched window (2026-05-20 00:00 to 2026-11-02 08:00): 2026-10-28 00:00.

## Dry run: open trades

_None._

MemeSleeveV3 trades in the dry run database, all time: 0.

## Provenance

Data: Binance spot public klines API (no keys), BTCUSDT 1d from 2023-01-01, DOGE/PEPE/SHIB/FLOKI USDT 4h last 1000 candles.
EMA computed TA-Lib style (SMA seed); BTC gate mapped to 4h candles as merge_informative_pair does (previous completed day).
Freqtrade's own data dir was not touched (claude-ops uses docker for read-only commands only).
Command: `python3 -I scripts/v3_gate_check.py > results/v3_gate_check_2026-11-02.md` (run as claude-ops from /root/trading-ops)
