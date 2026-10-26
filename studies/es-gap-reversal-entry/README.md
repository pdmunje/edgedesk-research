# Can waiting for a reversal improve ES gap entries?

Exploratory calculation and audit date: October 16, 2026. This follows the surviving-18:30 gap study using the same licensed minute archive. No selected rule is claimed validated. The original exploration used the entire available archive; chronological halves are reused dates, not an untouched test. An independent later-date test remains unavailable in this package.

## Reproduce with licensed input

Use Python 3.12 (checked with 3.12.14) and the pinned dependencies:

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input /your/licensed/archive.zip --output output
python -B verify.py --input /your/licensed/archive.zip --summary output/summary.json --output output/verification.json
```

The verification accepts optional `--original-trades /your/private/saved-trades.csv`. The included verification record used the private saved original trade file. It is excluded from this package; it is not needed for the new calculations. Omission records the historical audit as not performed.

ZIP contains exactly one CSV. Required columns:
`timestamp_utc, session_date, open, high, low, close, volume, underlying_contract, data_condition, is_complete, roll_transition`

UTC timestamps label minute starts, ordered and unique. Source `session_date` labels the morning date of an evening-to-afternoon futures session. Prices are finite, positive unadjusted prices of the named dated contract; high/low contain open/close. Volume is finite and nonnegative, with positive accumulated volume at every calculated point. Supplied bars must be marked complete; absent minutes are never synthesized. Degraded rows and roll-transition flags are screened as described below. Contract months are not spliced into an adjusted price series here.

Source SHA-256:
`b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`

707,321 rows, 518 source-session dates, August 28, 2024–August 28, 2026. Initial session is a one-minute fragment. Eligible morning dates and selection counts are in summary.json. Prices, raw volume, original vendor bars, private saved event/trade records and machine-specific paths are not distributed. Obtain your own licensed source. Other vendor or continuous-series construction need not reproduce the result.

## Eligible gaps and later outcome quality

All clocks are America/New_York. Target = required prior 16:59 minute close, known at 17:00. Monday–Thursday evening uses that same actual calendar date; Sunday uses exactly Friday. Do not substitute an older observed close. Initial gap = 18:00 open minus target. Require target and opening-window contract continuity, complete unflagged 18:00–18:29 bars and an available same-contract 18:30 opening record. Exclude zero gaps, target touches during those thirty minutes, or an 18:30 open already across the target. These price decisions use no later prices. Vendor flags are a retrospective data audit, not evidence of live flag availability.

The checked selection produces 131 reconstructed 18:30 signals. For this reversal study, the whole session must have all 1,380 consecutive same-contract, unflagged minute records starting 18:00–16:59. This leaves 120 full-day measurable gaps; 11 signals have unscored later outcomes. Full-day quality is an outcome-data restriction, never a condition known at 18:30. Missing outcomes are not zero-return no-trades. `gap_base.py` contains the prior checked qualification logic; `gap_recount.py` supplies an independent CSV/date recount.

## Five-minute decision bars and two weighted-price approximations

Group the exact consecutive minute records into bars 18:00–18:05, 18:05–18:10, etc. Each bar uses first open, maximum high, minimum low, final close and summed volume. A bar ending at 18:30 uses minute starts 18:25–18:29. All its inputs are known only once that bar ends. Reset calculations at each 18:00 opening, never across sessions.

Minute typical price = (minute high + minute low + minute close) / 3.
Minute-based running weighted price = sum(typical price × volume from 18:00 through the signal's final minute) / sum(volume over those same minutes).

Five-minute typical price = (five-minute high + five-minute low + five-minute close) / 3.
Five-minute-based running weighted price = sum(five-minute typical price × five-minute volume from 18:00 through signal bar) / sum(five-minute volume over those same bars).

These are candle-based approximations to volume-weighted average price (VWAP), not exact transaction-price VWAP. The minute approximation sampled at each five-minute close differs from averaging the five-minute candles themselves. No future bar or later volume enters a running average.

Original gap upper boundary = max(target, 18:00 open); lower boundary = min(target, 18:00 open).

For an initial up gap, every accepted signal close AND next-minute entry must remain above the upper boundary: the rule sells short from farther outside the gap toward the prior close. For a down gap, signal and entry must remain below the lower boundary and the trade buys toward the close. These are not generic price crossovers anywhere inside the gap.

## Four signal rules, fully specified

At a completed five-minute close, while the target has never touched in an earlier minute:

1. Minute-weighted-price rule (`vwap`): up gap, close below the minute-based running weighted price; down gap, close above it. This is a level condition, not a requirement to cross that average from the preceding close.
2. Five-minute-weighted-price rule (`vwap5`): same condition using the separately calculated five-minute approximation.
3. Candle-run opening-cross rule (`cisd` is the original code name): a close crosses the starting opening price of the latest run of candles in the opposite direction to the proposed trade. Use the state procedure below. For a short, that run's starting open must itself be above the original gap upper boundary; for a long, below the lower boundary.
4. Both (`both`): the minute-weighted-price condition and candle-run cross must occur on the same signal bar. It does not combine the five-minute approximation.

All four also require the outside-gap signal and entry conditions above. There is at most one executed trade per gap per rule per entry-window option. A qualifying signal with an invalid next open or invalid stop is skipped; continue scanning later completed signals until target touch or entry-window end.

### Exact candle-run state procedure

Track latest up-run opening price U and latest down-run opening price D, whether currently inside either run, and whether each anchor's crossing has already been used. Initially no anchors, no current runs, no used flags and no previous close.

For each five-minute candle in chronological order:

* If close > open: if not already in an up run, set U to this candle's open and clear its used flag; mark up run active. Otherwise mark up run inactive. Existing U persists when the run ends.
* If close < open: similarly start/continue a down run, storing D and its used flag. Otherwise mark down run inactive. Existing D persists after the run ends.
* Equal open/close ends both current runs but does not erase stored anchors or clear their used flags.
* Bearish crossing = U exists, unused, previous close >= U, current close < U. Bullish crossing = D exists, unused, previous close <= D, current close > D.
* Mark a detected crossing used immediately, even if it occurs before the permitted entry window or fails another trade condition. Save current close as the next previous close.
* A fresh same-color run replaces that color's anchor and re-enables a crossing. Anchor updates occur before this candle's crossing checks, exactly as in rules.py.

This prevents repeated entries from a close merely staying beyond an old anchor. The label is not enough to define the rule; the procedure above is its definition.

## Execution, scope, stops and costs

Signal ending at minute offset i is followed by entry at minute i's open, not at the signal's final close. First entry offset is 30 = 18:30. Next candidates are 35 = 18:35, etc. Require i < 1,380. For `overnight`, additionally require i < 930 = 09:30. Thus its last possible entry is 09:25. For `all_session`, the last possible entry is 16:55.

**Both entry-window options allow positions to remain open until 17:00.** “Overnight” in the original label restricts entry time, not exit time. These are not two different time-exit horizons.

Reject any signal whose next entry occurs after an earlier target touch. A target touch during the entry minute is allowed by the idealized simulation, but does not prove executable entry and target orders. Entry must still be outside the original gap boundary.

No-stop version: target at required prior close, otherwise 17:00 exit at the 16:59 minute close. Gross points = direction × (exit − entry), direction +1 long, −1 short. Net points = gross minus assumed total round-trip cost (main 1 point; also 0.5, 2 and 4 points). Costs are scenarios, not observed fees/spreads/slippage.

Stop version: short stop = highest high from 18:00 through completed signal bar + 0.25 points; long stop = lowest low over the same period − 0.25. This fixed stop is known at signal completion and is not trailed. Reject wrong-side or zero-distance stops. For each subsequent minute, first honor a known open beyond the stop at the worse opening price, or an open at/beyond target at target credit. Otherwise inspect high/low: if both stop and target touched, assign stop first; otherwise take the touched level. The exact opening price precedes unknown intraminute ordering. Other execution slippage is not modeled.

`simulate_legacy` preserves the older stop-first range treatment before opening-price sequencing for the optional old-record audit. The corrected current simulator handles known opening prices first. Reported ambiguity counts refer to unresolved range ties after opening checks.

## Denominators and sensitivities

Every rule has its own executed-trade denominator, with at most one trade per gap. Its target exits / its executed trades measure recorded target outcomes after entry. Stop target outcomes are separate because a stopped trade may miss a subsequent price touch.

Per-trade mean = total net points / executed trades. Median is the middle sorted result, averaging the two middle values for even n. Positive events are net points > 0. Mean per eligible gap including no-trade zero = total net points / all 120 measurable full-day gaps. No signal is zero in that allocation comparison, but an unavailable-data signal is excluded, not zero. This is not a compounded or capital-weighted account return.

The fixed-18:30 comparator enters every one of the same 120 eligible gaps without a stop, with target or 17:00 exit, after the same one-point cost. The paired mean difference compares reversal rule versus fixed entry on this common event list, assigning zero to a reversal no-trade. Different trade counts mean per-trade means are not directly comparable with per-gap means.

Removing each rule's largest net winner is a sensitivity check only. It uses the best result after observing the sample and is not a proposed executable exclusion. The stopped rule's largest winner is removed separately. Periods split at morning date August 29, 2025; all were already explored. The eight rule/window combinations overlap extensively, so they are not eight independent confirmations. No statistical significance or untouched-date performance claim is made.

## Files and verification

`results/summary.json` reports all eight combinations, costs, means/medians/totals, largest-winner sensitivity, stop outcomes, entry-time counts, chronological halves and paired per-gap allocation comparisons. `results/rule_summary.csv` summarizes all eight rows. `results/verification.json` records actual checks. No event-level market prices are exported.

`rules.py` preserves the earlier signal definitions and separates old/current simulation ordering. `gap_base.py` and `gap_recount.py` document and independently recount the prior gap qualification. `verify.py` separately constructs five-minute candles, running weighted prices, candle-run anchors, signals, target/stop paths and summarized trade outcomes. It compares current trade keys and core trade fields and optionally reproduces saved historical trade entries, prices and outcomes. Made-up fixtures test weighted averaging, candle-run crossing/single use, targets, stops, time exits, adverse stop gaps and known opening-price ordering.

The original source conversation was interrupted. Saved claims were treated as leads and rerun, not accepted as a finished assessment. Inputs and outputs are fingerprinted/checked without altering the licensed archive. The remaining research gap is a later, compatible licensed minute dataset not used for selecting or exploring these rules. Coarser candles cannot verify the minute sequencing and contract selection required here. No rule is recommended or promoted as independently validated.
