# Research: V3 on SOL and a possible MemeSleeveV4

Run date: 2026-11-02, as claude-ops (Abdullah approved `docker run` for this study on 2 Nov). Plan:
`docs/RESEARCH_V4_PLAN.md`, fixed before any test. Freqtrade 2026.9 (`freqtradeorg/freqtrade:stable`, image
sha256:9d67afb8eb5f), Binance spot, `backtest_config.json` (stake 25 USDT, wallet 1000 USDT, max_open_trades 2 unless
stated). Fee 0.1% per side, `--enable-protections`, `--breakdown month`, `--export none` unless stated.
Research only: the live container, `config.json` and `MemeSleeveV3.py` were not touched.

## Short answer
* **V3 unchanged holds up on the unseen window A (2020-08 to 2023-10).** It is profitable on every coin alone
  (PF 1.20 to 2.85) and as a basket (+58 USDT, PF 1.46). This is the first evidence for V3 from data nobody had seen.
* **SOL helps.** On A, SOL alone made +37.6 USDT (PF 1.69); on B +31.3 (PF 1.82). Adding SOL to the memes raised
  profit on A from +41.7 to +64.3 USDT with two slots. ETH is weak (PF 1.20 on A); BTC is steady but small.
* **Chosen variant: 5 (memes + SOL, 3 open trades).** It passes the bar in both windows and survives every stress
  test. Part of its gain is only more capital in use (75 instead of 50 USDT); per slot it is no better than V3.
* **Profit is thin and comes from bull runs.** Almost all of it is 2021 (A) and 2024 (B); 2022 and 2023 are flat
  or slightly negative. Holding the same coins made far more on A (+889% vs about +106% on capital in use).
* **Scale:** at 25 USDT stakes this is about +25 USDT a year. It does not change the income picture.

## Windows and data
* **A, unseen:** `--timerange 20200815-20231030`. Never used for any V1 to V3 decision.
* **B, seen:** `--timerange 20231030-20261030`. V3 was designed on it; used only to confirm.
* Downloads (2 Nov): `download-data --pairs SOL/USDT ETH/USDT BTC/USDT --timeframes 4h --timerange 20200101-`;
  `download-data --pairs DOGE/USDT SHIB/USDT --timeframes 4h --timerange 20200101- --prepend`;
  `download-data --pairs BTC/USDT --timeframes 1d --timerange 20200101- --prepend`; for phase 3
  `download-data --pairs SOL/USDT --timeframes 15m --timerange 20200801-` and
  `download-data --pairs DOGE/USDT SHIB/USDT --timeframes 15m --timerange 20200101- --prepend`.
* Data starts (Binance listing or 2020-01-01): BTC, ETH, DOGE 4h 2020-01-01; SOL 2020-08-11; SHIB 2021-05-10;
  PEPE, FLOKI 2023-05-05; BTC 1d 2020-01-01. 15m: DOGE 2020-01-01, SOL 2020-08-11, SHIB 2021-05-10, PEPE and FLOKI
  2023-06-01.
* **Correction to the plan:** PEPE and FLOKI were listed on 2023-05-05, so they exist for the last 6 months of A.
  The plan's coin list was followed anyway: on A, "memes" means DOGE and SHIB only.
* **Warm-up:** a pair tested alone is pushed back by 700 startup candles when its data starts late: SOL alone on A
  starts 2020-12-05, SHIB alone 2021-09-04. In multi-pair runs the window starts on 2020-08-15 but SOL and SHIB
  only trade once warm.

All commands below are in the form `docker run --rm -v /root/freqtrade/user_data:/freqtrade/user_data
freqtradeorg/freqtrade:stable backtesting --config /freqtrade/user_data/backtest_config.json --strategy MemeSleeveV3
--timeframe 4h --timerange <A or B> --fee 0.001 --breakdown month --enable-protections --export none --pairs <pairs>
[extra]`.

Column guide: **ex-best 2** = profit with the two best months removed (the plan's "no dependence on 1 to 2 months"
test). **DD** = max % of the 1000 USDT account underwater. **Market** = freqtrade's market change (average price
change of the pairs over the window).

## Phase 1: V3 unchanged

| Run | Pairs | Start | Trades | Profit USDT | PF | DD | ex-best 2 | Market | By year |
|---|---|---|---|---|---|---|---|---|---|
| A | SOL | 2020-12-05 | 58 | 37.63 | 1.69 | 1.66% | 1.46 | +1,554% | 20: −2.65, 21: 38.20, 22: −0.24, 23: 2.33 |
| A | DOGE | 2020-08-15 | 53 | 30.01 | 1.64 | 1.50% | 0.02 | +1,856% | 20: 1.80, 21: 34.75, 22: −1.15, 23: −5.41 |
| A | SHIB | 2021-09-04 | 29 | 11.73 | 1.55 | 1.26% | −4.93 | +10% | 21: 13.56, 22: 0.18, 23: −2.02 |
| A | ETH | 2020-08-15 | 62 | 7.53 | 1.20 | 1.07% | −4.70 | +306% | 20: 2.99, 21: 3.33, 22: 1.77, 23: −0.57 |
| A | BTC | 2020-08-15 | 48 | 38.84 | 2.85 | 0.70% | 18.48 | +188% | 20: 12.63, 21: 10.26, 22: 0.84, 23: 15.12 |
| A | basket of all 5 | 2020-08-15 | 165 | 58.02 | 1.46 | 2.07% | 14.63 | +632% | 20: 9.06, 21: 38.75, 22: −1.37, 23: 11.59 |
| B | SOL | 2023-10-30 | 60 | 31.34 | 1.82 | 0.82% | 11.43 | +197% | 23: 19.91, 24: 3.77, 25: 6.15, 26: 1.51 |
| B | ETH | 2023-10-30 | 66 | 18.27 | 1.54 | 0.63% | 0.25 | +26% | 23: 1.57, 24: 10.15, 25: 9.50, 26: −2.95 |
| B | BTC | 2023-10-30 | 58 | 12.28 | 1.64 | 0.35% | 1.25 | +128% | 23: 0.40, 24: 11.16, 25: 0.91, 26: −0.19 |

Reading: V3 works outside the data it was built on, in the sense that it is profitable everywhere. Single coins
lean on one or two months (DOGE, SHIB, ETH fail the ex-best 2 test alone); baskets spread that out.

## Phase 2: the six pre-declared variants, chosen on window A only

Selection rule, written down before phase 2 ran: among variants that pass the bar on A (profit, PF above 1.2, ex-best 2
positive), the one with the highest ex-best 2 profit wins; PF breaks ties. Memes on A = DOGE, SHIB.

Variants 4 and 6 change only strategy settings freqtrade accepts from config, so they were run with an extra
`--config` override file instead of new strategy files: variant 4 `{"trailing_stop_positive": 0.06,
"trailing_stop_positive_offset": 0.12}`, variant 6 `{"startup_candle_count": 1000}`. The log confirms each override.

| Variant | Pairs | Extra | Trades | Profit USDT | PF | DD | ex-best 2 | Passes on A |
|---|---|---|---|---|---|---|---|---|
| Baseline: V3 on memes | DOGE SHIB | | 82 | 41.73 | 1.61 | 1.62% | 4.54 | yes |
| 1 memes + SOL | DOGE SHIB SOL | | 131 | 64.32 | 1.53 | 3.11% | 9.52 | yes |
| 2 SOL ETH BTC | SOL ETH BTC | | 141 | 53.42 | 1.50 | 2.06% | 9.62 | yes |
| 3 memes + SOL + ETH | DOGE SHIB SOL ETH | | 164 | 72.45 | 1.56 | 2.59% | 15.87 | yes |
| 4 trail 6% after +12% | SOL ETH BTC | override | 166 | 24.56 | 1.21 | 1.87% | 3.96 | yes, barely |
| **5 variant 1, 3 trades** | DOGE SHIB SOL | `--max-open-trades 3` | 140 | **79.36** | **1.64** | 2.55% | **24.56** | **yes, chosen** |
| 6 variant 1, startup 1000 | DOGE SHIB SOL | override | 121 | 66.66 | 1.62 | 3.07% | 11.86 | yes |

* Variant 4: the tighter trail cuts profit to less than half of variant 2 on the same coins. Rejected on the numbers.
* Variant 6 differs from variant 1 only because 1000 startup candles start SOL about 50 days later (late January 2021
  instead of 2020-12-05); DOGE's trades are identical, so the BTC gate is unaffected. It says nothing about warm-up.
* **Capital caveat on variant 5:** it can have 75 USDT in play instead of 50. Per slot it made 26.5 USDT on A against
  variant 1's 32.2. The third slot adds capital in use, not edge. The real improvement is SOL.

**Variant 5 on window B, run once** (memes = DOGE PEPE SHIB FLOKI), with V3 as it runs live for comparison:

| Run | Pairs | Trades | Profit USDT | PF | DD | ex-best 2 | Market | By year |
|---|---|---|---|---|---|---|---|---|
| V3 live setup, 2 trades | DOGE PEPE SHIB FLOKI | 178 | 52.05 | 1.32 | 2.02% | 6.15 | +64% | 23: −12.13, 24: 53.60, 25: 6.37, 26: 4.21 |
| Variant 5, 3 trades | DOGE PEPE SHIB FLOKI SOL | 253 | 82.64 | 1.38 | 2.38% | 25.33 | +91% | 23: 0.21, 24: 61.17, 25: 10.97, 26: 10.26 |

The V3 row matches `freqtrade_v3.md` (+4.8% then +0.4% on the same 3 years), which checks the setup. Per slot:
27.5 USDT for variant 5 against 26.0 for V3. In B, SOL made +23.1 USDT and SHIB went from −7.2 to +1.4.

## Phase 3: stress test of variant 5

The EMA and breakout lengths are hard-coded in V3, so the neighbour runs used a scratchpad copy, `MemeSleeveV3P`
(`--strategy-path`), that reads them from environment variables with V3's values as defaults. Its only differences
from V3 are `EMA_LEN` (50), `HH_LEN` (20), `BTC_EMA_LEN` (100) replacing the three constants. At the defaults it
reproduces variant 5 exactly in both windows (A: 140 trades, 79.36 USDT; B: 253 trades, 82.64 USDT). The trailing
neighbours used config overrides as in phase 2. One setting changed at a time; all with `--max-open-trades 3`.

| Test | A profit | A PF | A ex-best 2 | B profit | B PF | B ex-best 2 |
|---|---|---|---|---|---|---|
| Variant 5 as chosen | 79.36 | 1.64 | 24.56 | 82.64 | 1.38 | 25.33 |
| Fee 0.2% per side (`--fee 0.002`) | 69.93 | 1.52 | 15.89 | 71.61 | 1.32 | 15.81 |
| `--timeframe-detail 15m` | 117.65 | 1.97 | 54.72 | 97.58 | 1.46 | 47.99 |
| EMA 38 (−25%) | 56.65 | 1.43 | 4.43 | 78.61 | 1.37 | 23.01 |
| EMA 62 (+25%) | 70.78 | 1.55 | 22.28 | 80.93 | 1.37 | 26.34 |
| Breakout 15 bars | 68.34 | 1.48 | 12.77 | 91.23 | 1.42 | 7.09 |
| Breakout 25 bars | 87.39 | 1.79 | 34.72 | 79.08 | 1.37 | 16.80 |
| BTC EMA 75 | 76.22 | 1.54 | 24.53 | 62.61 | 1.28 | 5.30 |
| BTC EMA 125 | 81.69 | 1.69 | 29.99 | 91.29 | 1.44 | 33.98 |
| Trail 7.5% (offset 20%) | 95.80 | 1.80 | 41.62 | 82.93 | 1.36 | 24.47 |
| Trail 12.5% (offset 20%) | 95.33 | 1.78 | 45.75 | 61.08 | 1.30 | 3.09 |
| Trail offset 15% (trail 10%) | 44.03 | 1.36 | 10.77 | 46.47 | 1.21 | 4.39 |
| Trail offset 25% (trail 10%) | 108.23 | 1.82 | 51.22 | 100.18 | 1.49 | 38.59 |

`lookahead-analysis --strategy MemeSleeveV3 --timeframe 4h --timerange <A or B> --fee 0.001
--targeted-trade-amount 100 --max-open-trades 3 --pairs <variant 5 pairs>`: **no bias** in either window
(100 signals each, 0 biased entry signals, 0 biased exit signals, no biased indicators).

Reading:
* All 24 runs stay profitable with PF ≥ 1.21 and positive ex-best 2. No cliff: it does not depend on exact settings.
* The thin spots are on window B: trail offset 15% (PF 1.21), trail 12.5% (ex-best 2 only 3.09), BTC EMA 75 (5.30).
  Shorter EMA 38 on A drops ex-best 2 to 4.43, with 2023 at −19.87.
* 15m detail gives more profit, not less: on 4h candles alone the backtest assumes the worse fill for the trailing stop.
* Phase 3 lengths were chosen by the plan (±25%), not tuned. Nothing here is a reason to change V3's settings.

By year (variant 5): A 2020 −0.85, 2021 +86.51, 2022 −1.19, 2023 −5.11; B 2023 +0.21, 2024 +61.17, 2025 +10.97,
2026 +10.26. Profit comes from bull runs; the BTC gate keeps the bear years near flat instead of making money in them.

## Phase 4: verdict

Bar to replace V3 (from the plan): profit in both windows, PF above 1.2, profit without the best two months positive.

| | Window A | Window B | Bar |
|---|---|---|---|
| V3 on memes (2 trades) | +41.73, PF 1.61, ex-best 2 +4.54 | +52.05, PF 1.32, ex-best 2 +6.15 | passes |
| Variant 5 (memes + SOL, 3 trades) | +79.36, PF 1.64, ex-best 2 +24.56 | +82.64, PF 1.38, ex-best 2 +25.33 | **passes, and passes the stress tests** |

**Against holding the same coins**, on the capital the strategy can have in play (75 USDT for variant 5, 50 for V3):
* A: variant 5 +79 USDT (about +106%) vs holding DOGE, SHIB, SOL about +889%. Holding wins by a mile, at the cost of
  the 2022 crash (drawdowns of 80 to 90% on these coins); the strategy's worst was 2.6% of the account.
* B: variant 5 +83 USDT (about +110%) vs holding +91%; V3 +52 USDT (about +104%) vs holding +64%. B is the window V3
  was designed on, so this is not evidence.

**Verdict:** variant 5 is better than V3 on both windows and robust to every stress test. Most of the gain is SOL; the
rest is one more slot of capital. It is still a small, bull-market strategy: about +25 USDT a year at 25 USDT stakes.

**What V4 would be:** variant 5 changes no strategy code. It is V3 with SOL/USDT added to the whitelist and
`max_open_trades` 3, both in the root-owned `config.json`. Per the plan, the live bot keeps V3 until at least 4
weekly reports exist and Abdullah approves the change; the change is his, as root.

**Update 2026-11-03:** Abdullah chose to move the dry run to variant 5 now, without waiting for the 4 weekly reports
(V3 had made no trades in its first 4 days). It runs as `MemeSleeveV4` (`fixes/freqtrade/MemeSleeveV4.py`): V3's
code with only the class name and header changed, so its trades are labelled V4 in the database.

## Limits
* Window A is one market cycle (2021 bull, 2022 crash). One cycle cannot prove an edge; it can only fail to disprove it.
* Results are in USDT on a 1000 USDT wallet with 25 USDT stakes; the profit % figures in freqtrade are of the wallet.
* Phase 3 ran on both windows; window B is design data for V3, so its stress numbers confirm, they do not choose.
* The scratchpad copy `MemeSleeveV3P` and the override files are not kept in the repository; their full content is
  described above.
