# Does waiting until 18:30 help an ES gap trade?

Calculation date: October 16, 2026. This exploratory follow-up separates a gap still open at 18:30 from a simulated trade entered then. All times use America/New_York. Morning-date labels identify sessions opening the preceding evening. This shares the same source and many events with related ES overnight, gap-profitability, gap-size and gap-timing studies; it is not independent confirmation.

## Reproduce

Use Python 3.12 (checked with 3.12.14) and your own licensed Databento-derived minute archive. Vendor bars and private saved event prices are not distributed.

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input /your/licensed/archive.zip --output output
python -B verify.py --input /your/licensed/archive.zip --summary output/summary.json --output output/verification.json
```

An optional `--original-events /your/private/saved-1830-events.csv` argument verifies the reconstructed old 122-event sample. The included verification record used this private file. It is not needed to reproduce the new calculations; omitting it records that the optional audit was not performed.

The input ZIP must contain exactly one CSV with:

`timestamp_utc, session_date, open, high, low, close, underlying_contract, data_condition, is_complete, roll_transition`

Timestamps are ordered, unique UTC minute starts. Prices are finite, positive, unadjusted dated-contract prices. High and low contain open and close. `session_date` is the source morning-date label. Boolean columns are true/false; `data_condition=degraded` and `roll_transition=true` flag a row. All supplied bars must be complete; absent minutes are not synthesized. Different vendor construction or contract selection may give different results.

Input SHA-256:
`b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`

The source contains 707,321 rows across 518 source-session dates, August 28, 2024–August 28, 2026. Its first session is a one-minute fragment. Measurable 18:30 events have morning dates August 29, 2024–August 27, 2026. Do not infer that later data was tested.

## Decision at 18:30; subsequent observation is separate

Target = the required prior 16:59 minute close, known at 17:00. Monday–Thursday evening uses the same actual calendar date; Sunday uses exactly Friday. Missing required calendar closes are not replaced with older observed closes. Target and current opening window must use the same dated futures contract.

Initial gap = 18:00 open minus target. Require 30 complete supplied minute records starting 18:00–18:29, a known 18:30 opening record, and an unflagged target and opening window. Only the 18:30 opening price and contract are used at the decision; its later high, low, close and quality flag do not select the signal. Past vendor flags are a retrospective audit of the input, not evidence that these flags were available live.

Skip zero initial gaps. For a positive gap, exclude if any first-half-hour low <= target; for a negative gap, exclude if any high >= target. Skip an 18:30 open that has already reached/crossed the target. Otherwise the gap remains open and a hypothetical fade (trade toward the prior close) is selected: short a positive initial gap, long a negative one. The direction does not switch.

Initial distance = abs(18:00 open − target).
Remaining distance = abs(18:30 open − target).
If remaining < initial: moved toward the close.
If remaining > initial: moved farther away.
If equal: unchanged.

517 evening candidates − 24 missing closes − 8 target contract mismatches − 9 unusable opening windows/boundaries − 26 zero gaps − 319 already touched − 0 crossed at 18:30 = **131 reconstructed decisions**. This selection never checks prices or coverage after 18:30.

After selecting them, require 900 consecutive same-contract, unflagged minutes starting 18:30–09:29 and a usable same-contract 09:30 opening boundary to score overnight outcomes. Eight signals lack that quality/coverage; they remain selected but are unscored. The main outcome tables therefore have **123**, not 131, events. Missing outcomes are not assigned zero return, wins or losses. This exclusion can bias the observed sample.

For daytime outcomes require all 1,350 same-contract unflagged minutes starting 18:30–16:59. This yields 120 measurable full-day events. This additional outcome restriction is also not a live signal. All 120 happen to have measurable overnight outcomes, permitting a matched-sample comparison.

## Hypothetical trade and costs

Entry = observed 18:30 open. Target = prior close. Direction d = +1 long, −1 short. Search minutes with start >= 18:30 and < 09:30. A long target is hit when high >= target; a short target when low <= target. A touch means reaching/crossing the level, not verified execution at it.

Without a stop, exit at target on a touch, otherwise at 09:30 open. Gross result = min(remaining distance, d × (exit − entry)); the cap prevents better-than-target credit if the time-exit opening price jumps beyond the target. Net result = gross result minus the assumed round-trip cost. Main cost is one point, with 0.5, 2 and 4 points also reported. These are scenarios, not measured fees or slippage. There is no account return, leverage, sizing, margin or compounding calculation.

Stop scenario 1 distance = max(remaining distance, 1 point).
Stop scenario 2 distance = max(2 × remaining distance, 1 point).
Stop level = entry − d × stop distance.

Stops apply from entry through 09:29; any position still open exits at 09:30 open. A minute that opens beyond the stop exits at that worse opening price. An open already beyond the target exits at target credit. If neither opening price determines an exit, inspect high/low; if both target and stop occur in the same minute, assign the stop first because their order is unknown. Otherwise use the first touched level. No unresolved both-hit minute or open beyond a stop occurred in the 123-event main sample, but the policy is tested on invented data. An opening exactly at the stop is an ordinary stop, not a worse gap execution. Other slippage is unmodeled.

Observing the 18:30 open and filling at the identical price is idealized. Two targets touched during the entry minute. A sensitivity enters at 18:31 only if the 18:30 minute did not touch and the target remains ahead of the new opening price. It has 121 events; its changed sample is explicit, not independent validation.

The 17:00 comparison uses the same target, no stop, minute starts through 16:59, then that final minute's close as the time exit. Compare it with 09:30 results only on the same 120 full-day events.

## Meaning of numbers

73/123 touch before 09:30. This differs from 76/123 positive net trades: some time exits earn money without a full touch, and a target gain can be smaller than assumed costs. Mean = sum of points / events; median = middle ordered result (average of two middle values for an even count). Best/worst are individual events, not account drawdown. The no-stop gross sum is −60 points and one-point costs subtract 123 more points, giving −183/123 = −1.487804878 points per event. All selected events are equally weighted, not volatility- or capital-weighted.

Among target-touch events, gross points total +856.75; among no-touch events, gross total −916.75. Six no-touch events still have positive gross time-exit outcomes. Positive touch frequency therefore does not guarantee a positive mean trade result.

The uncertainty check samples Monday–Sunday calendar weeks of the morning date with replacement, preserving all events within each sampled week. Draw the same number of observed event-containing weeks in each of 10,000 draws, seed 20261016; recompute the net point mean from pooled sums/counts. The 2.5th–97.5th percentiles form a 95% resampling range. It describes variability of this selected historical mean, not future trade outcomes or selection-adjusted evidence. Costs and execution remain assumed.

## Old sample and overlapping evidence

The old analysis first restricted the source using complete overnight and daytime coverage and current/previous whole-session degraded flags, then selected 122 surviving gaps. Its target could be the previous observed session close rather than the required calendar close. Fresh reconstruction matches all 122 saved events and eight values per event (976 matches): initial gap, remaining distance, first-touch offset, overnight touch flag, and gross outcomes for 09:30, 17:00 and two stop rules. Old no-stop mean after a one-point cost remains −1.50 points.

119 events overlap the current 123-event measurable sample. The three old-only morning dates are January 2, 2025, April 21, 2025 and January 2, 2026, where an older available close had been substituted. Four current-only events pass the revised window-specific quality rules. New signal selection is reported before future outcome-quality restrictions, rather than treating those restrictions as known at 18:30.

The earlier timing article used 389 complete full-day gaps: 269 had already touched before 18:30, leaving 120. Its 72/120 subsequent overnight touches describe the full-day subset here. The broader related 400-event overnight sample has 277 early touches, leaving 123 with 73 subsequent touches. These are overlapping samples of the same archive, not replication.

The original exploration also inspected gap-size/volatility thresholds and 30-minute bars from a different continuous series. This follow-up deliberately reports the basic surviving-gap decision, direction-of-movement groups, weekday and time-period checks, two explicit stops, delay and cost scenarios. It does not validate every old threshold, candle-reversal rule or continuous-series result. Coarser bars cannot settle minute execution or replace this archive's dated-contract checks.

## Outputs and verification

`results/summary.json` contains selection/outcome counts, all three rules, group and chronological checks, cost scenarios, matched full-day outcomes, delay, resampling settings and old-sample comparison. `results/group_summary.csv` summarizes the main group results. `results/verification.json` records actual checks. The source archive is fingerprinted before/after.

`verify.py` independently parses CSV with Python's standard library, selects all signals with datetime arithmetic, and scans price paths with separate target/stop logic. Every signal record and available outcome matches the pandas calculation. Aggregate statistics are recounted separately. Eleven made-up tests check target direction, time exits, stops, same-minute ties, adverse stop gaps, known target-side opens, target caps, exact-stop opens and that future flags change outcome availability without changing the signal selection. The resampling range itself is not independently recomputed.

Positive movement and weekday subgroups are retained, but were explored on the same data as the negative overall result. Earlier/later subgroup comparisons are descriptive; no untouched out-of-sample validation is claimed. Dataset flags, missing outcomes, vendor construction, contract rolls, minute sequencing and hypothetical fills limit interpretation.
