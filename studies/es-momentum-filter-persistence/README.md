# Which simple trend-and-momentum filter stays active longer?

Status: prepared for human review. Do not treat this package as a reviewed article release until its review is recorded.

## Question

Does a completed 15-minute/hourly combination give fewer short interruptions than a comparable filter updated every minute?

## Exact rules

Hourly version:

```text
direction_change = hourly EMA20 now − hourly EMA20 three hourly candles earlier
momentum = latest completed 15-minute close − close four 15-minute candles earlier
```

Minute version:

```text
direction_change = minute EMA1200 now − minute EMA1200 180 minute candles earlier
momentum = latest completed minute close − close 60 minute candles earlier
```

For either version:

```text
if direction_change > 0 and momentum > 0: allow longs
else if direction_change < 0 and momentum < 0: allow shorts
else: allow no new entries
```

Only completed candles contribute. Hourly direction changes only after a full clock-hour candle closes; 15-minute momentum changes at :00, :15, :30 and :45. These readings are held until the next update. The minute version updates each minute.

EMA update: `new EMA = previous EMA + (2 / (length + 1)) × (new close − previous EMA)`, seeded by the first close. Require 60 hourly observations or 3,600 minute observations before using the EMA, plus the older observations needed for its direction comparison. An additional check waits 100 hourly or 6,000 minute observations.

## What is measured?

An uninterrupted period is consecutive measured minutes allowing the same nonzero direction. One neutral minute ends it. A restart allowing the same direction is a new period. Periods already active at 9:30 are counted from 9:30; periods still active at 16:00 stop being measured there. These boundary cutoffs do not imply the indicator actually changed.

Main comparison: 342 days with a complete usable 09:30–16:00 America/New_York window for both versions. Signals available at each interval start are used: the 09:29 bar's finalized close supplies the 09:30 decision.

- Periods/day = total counted periods ÷ measured days.
- Middle length (median) = middle value after sorting all observed lengths.
- Short-period share = periods lasting at most 30 minutes ÷ all periods.
- Days with a 3-hour period = days containing any period of at least 180 minutes ÷ all measured days.
- Active-time share = minutes permitting longs or shorts ÷ measured minutes.

Results measure label persistence, not strategy profit. No complete entry/exit, cost or position-sizing system is specified.

## Reproduce

Python 3.12 was used for the original run. Required package versions are in `requirements.txt`.

```sh
python -m venv .venv
# Activate the virtual environment using your operating system's normal command.
python -m pip install -r requirements.txt
python reproduce.py --input /path/to/licensed-minute-export.zip --output output
```

The input can be a CSV or a ZIP containing exactly one CSV. The script reads it without modifying it. Do not upload generated minute prices, the input archive, or detailed local outputs to the public repository. Summarized results are provided under `results/`.

### Required columns

| Column | Meaning |
|---|---|
| `timestamp_utc` | Timezone-aware UTC minute-start timestamp, sorted and unique. |
| `open`, `close` | Original unadjusted ES price, numeric. |
| `underlying_contract` | Selected actual contract, such as ESU4. |
| `session_date` | Futures trading date; the prior 18:00 ET evening open belongs to the next trading date. |
| `roll_session` | Boolean marking the session when the selected contract changes. |
| `roll_transition` | Boolean true on the first row using the new selected contract. |
| `data_condition` | `available` for usable bars; other values are excluded. |
| `is_complete` | Boolean indicating the one-minute bar is complete. |

Input export: 707,321 minute rows, August 28, 2024–August 28, 2026, Databento-selected unadjusted ES contracts. ZIP SHA-256: `b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`.

That exact archive is privately owned and is not distributed here. The hash identifies it; it does not make it publicly available. Independently acquired data with the same schema may produce different results. No comparison between different inputs is claimed to be byte-for-byte reproduction.

### Data handling

Restart the calculations after a contract change, a bad/incomplete source observation or a missing minute inside a session. Do not fabricate replacement prices. Exclude sessions with any source-marked bad observations and require all 390 daytime minute bars. Then require both filters to have valid readings throughout all 390 decision intervals.

Ordinary session closures do not reset the EMA. EMA lookbacks count observed trading candles across scheduled closures. Momentum requires the two closes to be exactly 60 elapsed minutes apart. A higher-timeframe candle requires every constituent minute.

The main sample includes 342 of 485 clean full-day sessions; other clean days lack sufficient uninterrupted calculation history at every measured minute. The export contains 518 session dates in total.

## Additional checks

The script reports earlier/later sample halves, a longer EMA initialization period, an extended evening/overnight window, components swapped one at a time, a two-hourly-reading direction rule and minute calculations held to quarter-hour decision times. These variants were not selected by searching for the highest trading profit.

Boundary-adjusted lifetime estimates and later-price comparisons are extra diagnostics in the JSON; the article's main figures use observed daytime periods. Later-price comparisons are overlapping gross measurements, not independent trades or net profits.

## Reproduction record

Original arithmetic checks: `results/verification.json`. The portable script is rerun locally against the described source before review; its comparison record is stored with the results. All source-specific local paths have been removed.
