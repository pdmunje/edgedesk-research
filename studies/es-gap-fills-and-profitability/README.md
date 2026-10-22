# ES gaps often filled. Why did the simulated trade still lose?

Prepared October 15, 2026. Research calculation package, not verified execution.

## Question and answer

Main sample: 400 nonzero gaps, actual morning dates August 29, 2024–August 28,
2026. Target touches before 09:30: 350/400 = 87.5%. Mean simulated gross points
-0.043125; mean after a hypothetical one-point combined entry/exit cost -1.043125.
The 350 target-touch events sum to +1318 points, the 50 others to -1335.25.
203 events touch in the assumed entry minute. High touch frequency alone does
not imply profitable or executable trades. Data and strategy variants were
previously explored; this is not a fresh holdout or independent confirmation.

## Exact dates, prices and trading rules

All times use America/New_York. Timestamps label minute beginnings. The closing
reference is the 16:59 minute close, known at 17:00. Monday–Thursday evening
entries use that same calendar date's close. Sunday evening uses exactly Friday.
Missing required closes are not replaced by an older observed session.

Gap = 18:00 minute open - required 16:59 minute close.
Gap > 0: short; direction -1. Gap < 0: long; direction +1. Gap == 0: no trade.
Target = required prior close. Assume entry at the 18:00 minute open.
Long target touch: any minute high >= target. Short: any minute low <= target.
Search 18:00 through 09:29, ending before 09:30. If touched, credit absolute gap
size as gross points. Otherwise exit at the 09:30 minute open:

gross points = min(abs(gap), direction * (09:30 open - 18:00 open)).
net points = gross points - assumed combined entry-and-exit cost.

The target cap prevents better-than-target credit at a discontinuous time exit;
zero main-sample events actually need it. Two no-touch events have a positive
partial recovery at the time exit; consequently positive results (352) exceed
target touches (350). No stop-loss, sizing, reinvestment or account model.
The gap direction is known only when the reopen price is observed; assuming
an entry at that same price is explicitly idealized. A candle touch is not an
order-fill guarantee. No bid/ask, queue or order-acknowledgment data are available.

One event is one eligible nonzero gap. Average = sum / event count. Median is
the middle sorted value (average two middle values for even count). Positive
share = strictly positive results / all events *100; flats stay in denominators.
Touch share = recorded touches / all 400 events *100. Point sums check arithmetic,
not a compounded account return. Worst trade result is not maximum intranight loss.

## Eligibility, quality and zero gaps

707,321 source records, 518 source session dates including an initial fragment,
517 18:00 entry candidates. Sequentially remove 24 missing exact calendar target
closes, 8 target/entry contract changes and 2 missing 09:30 exits = 483 pairs.
Each retained 09:30 timestamp must be exactly 930 elapsed UTC minutes after
entry and have the same dated contract. Actual morning date must match source label.

Main window quality: require exactly 930 unique records 18:00–09:29, one dated
contract throughout, no degraded/roll-transition flag on those records, the
target minute or the 09:30 minute. 61 boundary-matched sessions fail quality;
dates, observed counts and flag reasons are in summary.json. That leaves 422;
exclude 22 zero gaps = 400 events. The next daytime need not be complete.
Quality checks include future records and are retrospective research diagnostics,
not conditions known at entry. Supplied complete bars can still have missing minutes.
Input timestamp order/uniqueness, positive finite OHLC and range consistency are checked.

Alternative full-day quality check: the same exact-date targets plus 930 overnight
records, 450 daytime records 09:30–16:59, and no degraded observation anywhere in
the current or previous observed source session. It uses a different roll-flag
policy from the main sample; these overlapping groups need not be nested.
It retains 384 nonzero events, mean +0.0130208 points gross, -0.9869792 after one
point. Main and alternative comparisons are not independent evidence.

The earlier script used a shifted observed-session close and had 387 events.
Our explicit target rule omits morning dates 2025-01-02, 2025-04-21 and 2026-01-02,
where no required calendar-date close exists. 384 common dates match all prior
touch flags and gross results (768 values). The older 387-event gross mean was
-0.0936693 points. This policy difference is disclosed, not silently combined.

## One-minute delayed entry diagnostic

Keep the original 18:00 target and direction. Skip if the 18:00 minute already
touched the target. Otherwise require exactly the 18:01 minute open, still on
the original side of target. Assume entry there, inspect 18:01–09:29 for target,
else exit at 09:30 open with the same target-profit cap. Here target profit is
direction * (target - 18:01 entry price), and the capped time result is the
smaller of target profit and direction * (09:30 open - 18:01 entry price).
203 main events are skipped; 197 remain, mean +0.3781726 gross points,
-0.6218274 after a hypothetical one-point combined cost. The rule and sample
have changed; this is not independent verification or proof of executable fills.
Order timing inside the new entry minute remains unobserved.

## Costs, periods and uncertainty

Assumed combined round-trip costs: 0.5, 1, 2 and 4 points per event, subtracted
once. These are scenarios, not actual broker fees or measured execution costs.
Group observations by Monday–Sunday calendar week of actual morning dates.
Resample the original number of observed weeks with replacement, keeping all
events in each selected week. Mean = sum / sampled event count. Repeat 10,000
times with NumPy seed 20261015; 2.5th and 97.5th percentiles form the range.
Constant costs shift the point mean/range by the cost. These ranges are for
historical means under the method, not future individual trades or probabilities
of strategy profitability. No correction for earlier parameter searches or
dependence beyond a week. Annual 2024 and 2026 groups are partial years;
earlier/later groups split at 2025-08-29. Neither period is an untouched holdout.

## Licensed input, schema and fingerprint

Provide your own permitted ZIP containing exactly one CSV with these columns:

* timestamp_utc: timezone-aware UTC minute-start time, ordered and unique.
* session_date: YYYY-MM-DD source futures-session/morning label.
* open, high, low, close: finite positive prices with consistent candle ranges.
* underlying_contract: dated futures-contract identifier.
* data_condition: source quality; `degraded` marks a problem.
* is_complete: boolean true for each supplied row, not proof no minutes are absent.
* roll_transition: boolean source contract-roll marker.

Source spans August 28, 2024–August 28, 2026.
SHA-256: b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c
The archive fingerprint is checked before and after calculation. Vendor prices
and upstream contract selection have not been independently audited. A checksum
identifies an input; it does not grant data access or redistribution rights.
Original market records, private event files and application code are excluded.

## Reproduction and verification

Tested with Python 3.12.14 and pinned dependencies in requirements.txt.
Run from this directory using your authorized source archive:

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_LICENSED_ARCHIVE.zip --output output
python -B verify.py --input YOUR_LICENSED_ARCHIVE.zip --summary output/summary.json --output output/verification.json
```

Only aggregate JSON/CSV outputs are written. The verifier parses CSV with the
standard library, independently pairs dates and paths, and recounts 403 numeric
values. Eleven invented-data tests passed, including multiple missing-date and
coverage scenarios. Mean ranges and vendor prices are not independently audited;
constant cost shifts are checked. Temporary fixtures are removed automatically.

Optional `--original-events EARLIER_EVENT_SUMMARY.csv` adds a comparison against
an earlier privately retained event file (requires session_date, filled_overnight
and pnl_overnight). It is not needed for any fresh calculation. Without that
optional input the original-event audit is marked not performed; the fresh
source recount and tests still run. No original per-event file is distributed.
The saved verification record documents the optional audit actually performed.

## Files and change record

* reproduce.py: focused target/time-exit calculation.
* verify.py: separate CSV/date/path recount and invented mechanics tests.
* requirements.txt: pinned numpy, pandas and tzdata.
* results/summary.json: aggregate samples, exclusions, variants, costs and ranges.
* results/annual_summary.csv: annual count, touch share and simulated mean.
* results/verification.json: actual checks, original-event comparison and limits.

October 15, 2026: first research draft, explicit calendar targets, window-based
quality checks and separate older full-day-policy comparison. Same-minute fills,
costs and negative averages are explicit. Human approval is not inferred from
passed calculations; the owner reviews the exact version in Studio.
