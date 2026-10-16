# Does checking an intraday signal less often reduce interruptions?

Prepared for human review. This follows the ES momentum-filter study using the same input, calculation settings and eligible dates. It is not independent evidence or a trading-profit test.

## What changes?

Both versions calculate the same underlying signal after each completed minute:

```text
EMA = previous EMA + (2 / 1201) * (new minute close - previous EMA)
direction_change = EMA now - EMA 180 observed minute candles earlier
momentum = latest minute close - close 60 elapsed minutes earlier

if direction_change > 0 and momentum > 0: decision = +1 (allow longs)
else if direction_change < 0 and momentum < 0: decision = -1 (allow shorts)
else: decision = 0 (allow no new entries)
```

The EMA is an exponential moving average: recent closes receive more weight. Seed it with the first close; require 3,600 observations, then another 180 for the older EMA comparison. These are initialization rules, not an assertion of exact convergence. The underlying analysis also requires the hourly and 15-minute components of the first study to be available throughout each selected day. This preserves its exact matched sample rather than broadening the sample for this follow-up.

Every-minute version: use the newest completed-minute decision immediately.

Every-15-minute version:

```text
at :00, :15, :30, :45:
    stored_decision = newest completed-minute decision
between these times:
    use stored_decision, including when it is zero
```

This holds the combined decision; it does not recalculate the EMA from 15-minute candles. It does not ask for two confirmations or impose a minimum trade duration. An underlying reversal between check times is ignored until the next check. No zero is skipped. All times are America/New_York; UTC timestamps are used internally. Quarter-hour boundaries coincide in both zones during this sample.

## Made-up timing example

The signal permits longs at 10:00. It pauses for one minute at 10:07, then permits longs again at 10:08 and 10:15. Through 10:30, the every-minute version has two periods of 7 and 22 minutes, separated by one neutral minute. The held version has one 30-minute period. The 10:07 pause remains real in the underlying signal; the held decision ignores it. Conversely, a neutral reading at 10:15 would remain neutral until 10:30, even if the underlying signal resumed at 10:16.

## What gets counted?

Measure the 390 one-minute intervals from 09:30 inclusive to 16:00 exclusive on each eligible day. The close of the 09:29 minute supplies the 09:30 decision; the 15:58 close supplies the decision at 15:59. The minute starting 15:59 supplies a later decision at 16:00, outside this measurement window.

A period is consecutive measured minutes permitting the same nonzero direction. Neutral ends a period. A direct direction change ends one period and starts another. The same direction restarting after neutral is another period. Split periods at each day's boundaries. Periods already active at 09:30 and still active at 16:00 are counted only for their observed portions. Thus lengths are window-clipped measurements, not complete lifetimes.

- Periods per day = total periods / eligible days.
- Median length = middle observed period length (mean of middle two if the count is even).
- Share at most 30 minutes = periods with observed length <= 30 / all observed periods.
- Active-time share = active minutes / all measured minutes.
- Days containing a 3-hour period = days with at least one observed length >= 180 / eligible days.
- Decision disagreement = minutes the two versions show different decisions / all measured minutes, including neutral minutes.

`daily_counts.csv` contains one row per method per day. `periods` includes portions clipped at day boundaries; `longest_period_minutes` is zero if no active period occurs. Earlier/later halves split the selected dates at the middle selected date; this is a descriptive consistency check using overlapping first-study data, not an untouched holdout.

## Input and exclusions

Read a CSV, or ZIP containing exactly one CSV, with these columns:

| Column | Meaning |
|---|---|
| timestamp_utc | Unique, timezone-aware UTC minute-start timestamp |
| open, close | Numeric unadjusted ES prices |
| underlying_contract | Selected actual futures contract |
| session_date | Futures trading date, including its preceding evening |
| roll_session | Boolean: selected contract changed during this session |
| roll_transition | Boolean: first row using the newly selected contract |
| data_condition | `available` for usable bars; other values are rejected |
| is_complete | Boolean: this minute candle is complete |

The documented licensed archive contains 707,321 rows, August 28, 2024 through August 28, 2026, across 518 session dates. It uses Databento-selected unadjusted ES contracts. Archive SHA-256: `b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`. The fingerprint identifies the private file; it does not grant access to it.

Of 518 source session dates, 485 have all 390 daytime bars and no source-marked bad observation anywhere in that session. Of those 485, 342 have valid calculation history throughout all 390 daytime decision intervals for every original comparison component. Those same 342 days are used here. Do not describe this as evidence through October 2026 or as every trading day in the archive.

Restart indicators on a contract change, unusable observation, or a missing minute inside a session. The archive has eight contract transitions, 8,846 unusable rows across 13 dates, and 96 within-session timestamp breaks. Scheduled session closures do not reset the EMA; its lookbacks count observed trading bars across those closures. Momentum endpoints must be exactly 60 elapsed minutes apart. Do not interpolate missing bars. Higher-timeframe candles used for shared sample eligibility need every constituent minute. No original vendor prices are redistributed.

## Reproduce and check

Verified environment: Python 3.12.14; dependency versions are pinned in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python -B check_examples.py
python -B reproduce.py --input /path/to/licensed-minute-export.zip --output output
```

The wrapper runs the unchanged `base_analysis.py` from the first study, then independently recounts both versions' periods from its minute signals. It checks 18 summary values against that calculation, complete daily intervals, quarter-hour-only changes, and reconciliation of disagreement categories. Intermediate minute signals include prices, live in a temporary directory and are removed when the wrapper exits. The wrapper writes only `summary.json` and `daily_counts.csv`. Running `base_analysis.py` directly produces detailed private outputs; never upload them.

Five made-up checks cover the one-minute pause, holding zero, switching directions and counting day-edge portions. They check mechanics, not market performance. The independent recount shares the first study's calculated signals and therefore does not independently validate the vendor input or every EMA reading. The earlier study's separate arithmetic checks remain relevant but are not new independent evidence here.

`results/verification.json` records the actual rerun and comparisons. No original source file was changed. Independently obtained inputs can produce different numbers; do not claim an exact reproduction without matching the fingerprint and summarized outputs.

## What this does not establish

There are no entries, fills, stops, exits, sizing, costs or profit estimates. Holding decisions mechanically removes possible changes between checks, including useful responses to new information. At a one-minute decision resolution the maximum delay to the next check is 14 minutes. A 15-minute minimum observed period in the held version is imposed by the schedule, not discovered as a market tendency. Other check schedules and trading performance are untested here.

The companion base calculation retains the original study's extra variants and later-price diagnostics to preserve the exact source. This article's output uses only the minute signal, its quarter-hour-held version and the documented sample selection; those extra diagnostics are not trade results presented by this follow-up.
