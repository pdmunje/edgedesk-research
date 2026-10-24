# When do ES reopen gaps first return to the prior close?

This is a descriptive timing study, not a simulated trading return. Calculation date: October 15, 2026. All displayed clocks use America/New_York. Event dates are the morning date, so a Monday event opens Sunday evening.

## Input and reproduction

Obtain your own licensed Databento-derived ES one-minute archive. Original vendor bars and private saved event prices are not distributed. The ZIP must contain exactly one CSV with ordered, unique UTC minute-start timestamps and these columns:

`timestamp_utc, session_date, open, high, low, close, underlying_contract, data_condition, is_complete, roll_transition`

Prices are positive, finite, unadjusted prices for the named dated futures contract. High/low must contain open/close. `session_date` is the source morning-date label. Booleans are true/false. `data_condition=degraded` or `roll_transition=true` flags a row. All supplied bars must be complete; absent minutes are handled by the window checks. Other data or a different continuous-contract construction will not necessarily reproduce these results.

Source ZIP SHA-256:
`b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`

The source has 707,321 rows across 518 source-session dates, starting August 28, 2024 and ending August 28, 2026. The initial session is a one-minute fragment. The eligible event morning dates are August 29, 2024–August 28, 2026. Timestamps are converted to New York time using timezone rules; the observed evening-to-next-afternoon window must have 1,380 consecutive minutes. No synthetic bars are filled in.

Use Python 3.12 (checked with 3.12.14):

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input /your/licensed/archive.zip --output output
python -B verify.py --input /your/licensed/archive.zip --summary output/summary.json --output output/verification.json
```

`--original-events /your/private/saved-events.csv` is an optional verification argument. It compares the reconstructed old sample with the saved event file; the file is not necessary to reproduce fresh results. That audit was performed for the included verification record. An independently reproduced record without the private file will say the optional audit was not performed.

## Exact event and target rules

1. Find an 18:00 opening record. Monday–Thursday evenings use the same actual calendar date's 16:59 minute close; Sunday evening uses exactly Friday's 16:59 minute close. This close is known at 17:00. Never substitute an older available close. Reject a target/entry dated-contract mismatch.
2. Observe minute bars starting at 18:00 through the next day's 16:59. Require all 1,380 consecutive minutes, one unchanged dated contract across the whole window, and no flagged row in the window or target minute. This is a retrospective data-quality restriction, not a live entry signal. The entire prior session need not be unflagged: only its target minute is used.
3. Gap = 18:00 open minus required prior close. Skip zero gaps.
4. If gap is positive, the first minute with low <= target is a touch. If gap is negative, use high >= target. Touch means reaching or crossing the target in the recorded range; it does not require a transaction at the exact target price.
5. `minute` is the integer offset of that first minute's start from 18:00. No recorded touch before the next 17:00 is a separate outcome. Do not infer that the gap never fills afterward.

For cutoff m, count `first touch minute < m`. Minute zero is [18:00,18:01); the first half-hour comprises minute starts 18:00–18:29. A first touch in the 18:30 minute is outside that half-hour. Minute 930 is [09:30,09:31) and is daytime, not overnight. Midnight is offset 360, and the 16:59 minute ends the 1,380-minute horizon. We cannot identify the second of a touch. Crossed target levels do not prove orders would fill.

## Samples, counts and denominators

517 evening candidates − 24 missing required closes − 8 target contract changes − 67 missing/misaligned full days − 8 flagged or mixed-contract full days − 21 zero gaps = **389** events. Exclusions are sequential, so reasons are not double-counted. There are 410 eligible full-day sessions including zero gaps.

197/389 touch in the first minute, 269/389 before 18:30, and 341/389 before 09:30. Another 19 first touch during 09:30–17:00. 29 have no recorded touch in the horizon. These disjoint outcomes sum to 389. Of the 341 overnight touches, 269/341 occurred before 18:30. That conditional percentage uses 341, not all 389 gaps.

For a waiting-time diagnostic, remaining gaps at m = no touch before m, including those that never touch within the horizon. Later overnight touches = m <= first touch minute < 930. Percentage = 100 × later touches / remaining gaps. At 18:30 this is 72/120 = 60%; it is not a result for entering a trade at 18:30. Remaining gaps differ in size and weekday composition.

The same source supplies a broader **400-event overnight-only comparator** with full 930-minute overnight coverage, unflagged target/overnight/09:30 boundary and the same dated contract. It has 277 half-hour touches and 350 overnight touches. All 389 full-day events are shared with it; the other 11 lack the stricter full-day qualification. Daytime results are not inferred for those 11.

## Reconcile earlier research

The old saved sample had **387** complete, nondegraded events. It used the previous observed source-session close, checked current and previous whole-session degraded flags, and required 930 overnight plus 450 daytime minutes. Its overnight path had to retain the entry contract; its full daytime path and roll flags were not checked the same way as the new policy. Fresh reconstruction matches all 387 dates, gap sizes and first-touch minutes against the private event file. It yields 193 first-minute, 225 first-five-minute, 265 first-half-hour, 338 overnight, 20 daytime-first and 29 no-touch outcomes.

The new and old samples share 384 events. Three old events used an older available close where the required calendar close is absent (morning dates January 2, 2025, April 21, 2025, January 2, 2026). Five new events are permitted by checking the actual target minute rather than rejecting an unrelated degraded minute elsewhere in the previous session. These changes explain 387 − 3 + 5 = 389. They are alternative data policies on largely the same events, not independent evidence.

An older general gap summary used `minute <= 5` and `minute <= 60`, counting the 18:05 and 19:00 minute bars. That produced 231 and 281, respectively. The saved timing-specific analysis and this study use `< 5` and `< 60`, giving 225 and 280 in the old 387-event sample. The definition, rather than a market change, explains this boundary difference.

## Outputs and verification

`results/summary.json` contains all time cutoffs, disjoint time buckets, changing-denominator waiting diagnostics, Sunday/weekday groups, four gap-size groups, two chronological halves, selection counts, source fingerprint and sample overlap. `results/cumulative.csv` is the full-day cumulative table. `results/verification.json` records the actual checks.

`verify.py` reads the archive independently with the standard-library CSV reader and datetime arithmetic. It compares every selected event's date, gap and minute offset with the pandas calculation, recounts the displayed aggregates and percentages, and runs eleven made-up tests covering touch direction, absent touches, minute-zero, exact cutoff exclusion, full coverage, missing daytime bars, daytime flags, daytime contract changes, zero gaps and missing calendar targets. Source bytes are fingerprinted before and after.

No confidence intervals or predictive probability estimates are claimed. Weekday, size and chronological splits are descriptive checks selected after related gap exploration. Counts can depend on the vendor's trade bars, contract selection, holiday handling, data-quality flags and source date labels. First-minute order sequencing, spreads, fees, slippage, stops, position size, account returns and margin are not modeled. Coarser historical slot candles cannot establish exact minute timing and are not pooled into this study. Related gap and overnight articles use the same archive and overlapping events.
