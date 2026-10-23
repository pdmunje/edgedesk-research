# Do larger ES gaps make better trades?

Prepared October 15, 2026. Research-only reproducible package.

## Finding and its limits

No tested full-period threshold has a positive average simulated result after
the assumed one-point round-trip cost in either source. Larger minimum gaps
are rarer and generally touch their target less often. Recent >=10-point gaps:
62/422 eligible sessions; 29/62 target touches; mean net -5.580645 points.
Recent all nonzero baseline: 400/422 sessions, 350/400 touches, mean net -1.043125.
This is not a dependable trading rule. The >=2-point later minute year is positive
(110 events, +2.397727 mean net), while the earlier year is negative (97 events,
-5.234536 mean net). Both years were already explored, not a fresh holdout.

## Gap and target/time-exit rule

Use America/New_York clock labels and UTC elapsed-time checks. Minute records
are timestamped at their beginning. Target = close of the 16:59 minute, known
at 17:00. Monday–Thursday 18:00 entries use that same calendar day's close;
Sunday uses exactly Friday's. A missing required close is never replaced by
an older observed close. All minute references/path use the same dated contract.

Gap = 18:00 open - required close; size = abs(gap). Nonzero gaps only are traded.
Gap >0: short, direction -1; gap <0: long, direction +1.
Search 18:00–09:29 minute highs/lows: long touch high >= target, short low <= target.
If touched, gross points = abs(gap). Otherwise gross = min(abs(gap), direction *
(09:30 open - 18:00 open)). Net points = gross - 1 assumed combined entry/exit point.
The time-exit cap never credits more than the target profit. No stop, sizing,
margin, reinvestment or account model. A recorded touch does not guarantee a fill.
The gap is known only after observing the reopen; entry at that same open is
idealized. Some targets touch within the entry minute. Actual costs are unmeasured.
Gap size must exceed assumed cost for strictly positive target profit; this
necessary arithmetic condition is not sufficient for a profitable average.

## Observed range and 14-session ATR

Source-session range = observed high - observed low over its entire source date,
usually prior evening 18:00 through its 16:59 minute. It is not RTH-only movement.
For each source session with an opening record, true range = max(range,
abs(high - previous observed source-session close), abs(low - previous close))
when that close exists, the current session has one consistent dated contract
(or historical source/segment), and the previous actual closing label matches.
Missing continuity labels also use own range, rather than assuming a comparable
previous close. Otherwise true range = own observed range. A mixed-source observed range can
still be distorted. Skip source fragments with
missing opening records, including the minute archive's initial one-minute fragment.

Seed ATR with the mean of the first 14 true-range updates. Thereafter:
ATR_new = (13 * ATR_previous + true_range_latest) / 14.
This is Wilder smoothing and retains diminishing weight from older records,
not an arithmetic moving mean of only the latest 14 ranges. Missing/short-session
observations can understate range and still update the main ATR. When a fragment
is skipped, no update is made and the next comparison starts without a prior close.

For each gap, use the required prior closing session's range and ATR, and assert
that its last record ends before the minute entry (or no later than the slot entry).
No current/future session high or low enters the scale.
Range fraction = abs(gap) / prior range. ATR fraction = abs(gap) / prior ATR.
0.10 means 10% of the movement scale, not 10% of the ES price.
ATR is unavailable until its seed exists; zero/nonpositive unavailable scales
are not used. Initial fragment is excluded rather than seeded as a complete day.

Strict recent diagnostic: latest 14 updates each have 1380 observed minutes,
one dated contract and no degraded/roll flag. Only 56 eligible sessions remain,
including 51 nonzero events. This diagnostic does not erase older records still
weighted in ATR; it is small, retrospective and overlapping, not a live filter.

## Thresholds, denominators and uncertainty

Point thresholds: .25, .5, 1, 2, 3, 5, 8, 10, 15, 20, 30, 50.
For each of range fraction and ATR fraction: 0, .01, .02, .03, .05, .075, .1,
.15, .2, .25, .3, .4, .5, 1. All comparisons use >=; zero gaps never trade,
even at threshold 0. Rows are cumulative, overlapping and previously explored.
No threshold is chosen as optimal. There are 40 rows per source, another 40
for the recent diagnostic and five explicitly labelled two-point period checks.

Frequency = selected nonzero events / all eligible scale-available sessions *100.
Touch share = touched selected events / selected events *100.
Mean = sum of selected results / selected count, equal weight per event.
Positive share includes zero results in its denominator, but numerator is >0.
Median is the middle sorted result, averaging two middle values when needed.
Gross means before costs; net means after the assumed fixed one-point deduction.
Point sums/means are not compounded account returns. Worst point result is not
maximum within-position loss. Input quality uses later records retrospectively.

Minute frequency denominators: points 422, range 421, ATR 412; corresponding
nonzero baselines 400, 399, 391. Warm-up and absent range change the sample;
do not credit normalization for differences between unequal-date baselines.
Historical denominators: points/range 2248, ATR 2237; nonzero 2007/2007/1997.

For each threshold, group selected events by Monday–Sunday calendar weeks of
actual morning dates. Draw the original number of selected-event weeks with
replacement, keep all selected events in each drawn week, and compute sum/count.
Repeat 10000 times, seed 20261015. Percentiles 2.5/97.5 form a 95% historical
mean range; subtract the same constant cost from endpoints. No adjustment for
searching thresholds, longer-than-week dependence, data errors or unverified fills.
Intervals are not predictions for individual future trades or profitability odds.

## Input A: licensed minute archive

ZIP containing exactly one CSV. Required columns: timestamp_utc (timezone-aware
UTC minute start), session_date (YYYY-MM-DD morning label), open/high/low/close
(finite positive consistent candle prices), underlying_contract (dated contract),
data_condition (`degraded` marks a problem), is_complete (boolean true on supplied
rows), roll_transition (boolean source flag). Rows are ordered and unique.
707321 records, source dates August 28, 2024–August 28, 2026; eligible gap morning
dates August 29, 2024–August 28, 2026. 517 evening candidates minus 24 missing
exact closes, 8 contract changes, 2 missing morning exits = 483 boundary pairs;
61 fail window coverage/quality = 422, including 22 zero gaps.

Main quality: exactly 930 minutes 18:00–09:29 and separate exact 09:30 open,
one contract throughout, no degraded/roll flag on target, path or exit record.
The JSON preserves dated exclusions. Supplied complete bars do not imply no
minutes are absent. No full following daytime is needed for the 09:30 exit.
SHA-256: b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c

## Input B: licensed historical time-of-day slot CSV

Required columns: time/end_time (timezone-aware ISO start/end), trade_date
(morning YYYY-MM-DD), slot_id (T01–T13), open/high/low/close (observed block prices),
observed_minutes (count), eligible (boolean), roll_segments (continuity label,
can be missing), source (source label). Expected block minutes in T01–T13 order:
120,240,120,60,180,150,60,60,90,120,90,30,60. Seven overnight blocks sum 930;
six daytime blocks sum 450. Clock spans must be contiguous and match durations.

Require all 13 blocks eligible, >=95% observed-minute coverage separately
overnight/daytime, 18:00 entry and following 09:30 block-start reference exactly
930 elapsed minutes later. Target is the eligible block ending at 17:00 on the
required calendar date; same source/roll-segment labels must join it with the
overnight path and morning boundary. Missing segment labels can match as missing;
this does not independently establish the upstream contract construction.

32499 blocks across 2522 source dates. Sequentially exclude 130 slot/coverage,
92 missing exact target, 52 eligibility/continuity = 2248 eligible sessions,
including 241 zero gaps. First/last eligible morning: 2017-01-04 / 2026-10-06.
Missing minutes may hide touches or change a boundary reference. Block open/close
does not prove exact minute trades at every older nominal boundary.
SHA-256: 4ba7344c2529beeda8978c6694120f694148387f2759be2efe5d70fabacb6385

406 eligible session dates overlap, including 385 nonzero events. Gap, target
touch and gross point result agree there. Never add shared dates as independent
evidence; price/path agreement does not imply identical volatility inputs.
The old saved study used different observed-row/continuity rules; its counts and
claims are leads, not silently reused fresh results. All outputs here were rerun.

## Reproduce and verify

Python 3.12.14 with pinned requirements. Keep all four Python files together.
Supply your own permitted inputs; these licensed records are not distributed.

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_LICENSED_MINUTES.zip --history-input YOUR_LICENSED_SLOTS.csv --output output
python -B verify.py --input YOUR_LICENSED_MINUTES.zip --history-input YOUR_LICENSED_SLOTS.csv --summary output/summary.json --output output/verification.json
```

Only aggregate outputs are written. Both input fingerprints are checked before
and after calculation. Independent standard-library CSV/date/path and volatility
code matches 2864 numerical values. Eleven invented tests cover seed/recursion,
roll fallback, fragment exclusion, future-record protection and denominators.
Mean intervals and vendor prices are not independently audited.

Files: reproduce.py (size/scales), gap_base.py (portable gap/path helpers),
verify.py (independent volatility/threshold checks), gap_recount.py (independent
minute parser), requirements.txt, results/summary.json (all grids/diagnostics),
results/threshold_summary.csv (80 main-source rows), results/verification.json.
No original bars, private event files, application code, credentials or raw chats.
Fingerprints identify inputs; they do not grant data access or redistribution rights.

October 15, 2026: first size-threshold draft with explicit calendar targets,
observed-range caveats, fragment-excluding ATR seed, correct frequency denominators
and source overlap. Later-year positive and full-period negative findings retained.
Human publication approval is not asserted; the owner reviews the exact Studio version.
