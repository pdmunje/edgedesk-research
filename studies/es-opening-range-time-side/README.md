# Does an opening-range setup depend on time and trade direction?

Prepared October 21, 2026. A historical follow-up to the opening-range sweep study.
Research-only files: no original prices, account data, article/card renderer or private application code.

## Finding

Of 60 original-assumption development choices, 7 had a positive later mean after
the assumed costs. Under stricter coverage/execution assumptions, 9 of 59 did.
Only 3 of the 11 stricter groups with a positive development mean were also
positive later. The stricter later trade-weighted mean was -0.62824 points over
20,774 overlapping simulated trades; the equal-group mean was -0.65764 points.
No selected later day-resampled 95% mean range was wholly above zero.
The missing strict group is the full-session long: no candidate reached 100
development trades. Groups overlap and later dates were already examined.
This does not establish a dependable future rule or executable combined portfolio.

## Question and exact selection rule

The earlier study pooled each window family across start times. This follow-up
separates every family, New York start time and long/short direction. It keeps
every group rather than reporting only the best-looking clock hours.

For each group and execution model, consider the original opening-range lengths
(1/2/5 minutes for hourly windows; 1/2/5/15/30 for the other families) and prior
range-average lengths (9/14 completed windows). Keep candidates with at least
100 trades on 2016–2022 session dates. Choose the highest mean net points per
trade on those development dates. Resolve exact ties by more trades, shorter
opening range, then shorter range-average length. A group with no qualifying
candidate gets no selected rule. Negative development winners remain visible.
Apply each chosen definition unchanged to 2023 onward. These later dates were
already explored in the old study, so they are not an untouched future test.
No choice uses later results; that does not undo earlier exploration of the data.

## Windows, prices and execution

All clock times follow America/New_York daylight-saving rules. Futures sessions
run 18:00 through 17:00 the next day, with 17:00–18:00 removed. Label each session
by its morning date. Hourly windows start at 18:00, 19:00, ..., 16:00 (23 starts).
Full four-hour windows start 18:00, 22:00, 02:00, 06:00 and 10:00. The 14:00–17:00
three-hour piece is not a four-hour trading group. The other families are
18:00–09:30 (930 minutes) and 18:00–17:00 (1,380 minutes). There are 60 possible
family/start/direction groups: 46 hourly + 10 four-hour + 2 overnight + 2 full-session.

Opening-range high/low = maximum high/minimum low in the initial chosen minutes.
For a long, first observe a later minute touching the range low, then a strictly
later minute closing above the range high. Reverse upper/lower for a short.
The touch must occur after the initial range and before the confirming minute;
same-minute touch and breakout do not suffice. Use only the first qualifying
trigger, with at most one trade per direction and parent window.

True range = max(high-low, abs(high-previous close), abs(low-previous close)).
The first window of a fresh history uses high-low. Seed the range average with
the mean of 9 or 14 true ranges. Thereafter:
new average = (previous average * (length-1) + latest true range) / length.
The current window can use only the average from prior completed windows.

Long raw stop = min(parent open, opening-range high - prior range average).
Short raw stop = max(parent open, opening-range low + prior range average).

**Original-assumption replay:** at least 90% minute coverage, exact first minute,
last minute no more than two minutes before the window end, complete initial
range, one dated contract. Enter at the confirming close. Stops can be fractional
ticks and become active on the following minute. Exit at the stop, a worse
gap-through open, or the final available close. The range-average history can
contain incomplete windows and the final three-hour four-hour-family piece.
These assumptions reproduce the saved analysis, not an endorsement of execution.

**Stricter replay:** every expected minute, one dated contract and one source
roll segment; prior range-average history resets after an observed incomplete
window or roll segment change. Omitted/unobserved whole windows are not invented
or automatically treated as observed bad windows. Exclude the three-hour piece
from both range averages and trades. Enter at the next minute open; cancel if
no next minute exists or its open is at/beyond the planned stop. Round a long
stop down and a short stop up to the 0.25-point tick. The stop is active during
the entry minute. Use the worse open for a gap through the stop, otherwise the
stop price; if not stopped, use the final window close. No rearming after cancellation.

Both replays subtract 0.59 ES points per completed trade: one 0.25-point tick
on each side plus $4.50 / $50 per point = 0.09 points commission. This is an
assumption, not measured execution or a current broker quote. One ES point is
$50 per contract; there is no sizing, compounding, portfolio or live fill simulation.

## Measurements and uncertainty

Mean net points per trade = sum(gross points - 0.59) / completed trades.
Positive-trade share = trades with net points > 0 / all trades. Flat trades stay
in the denominator. A positive-group share instead counts selected definitions
with positive mean net points divided by selected groups; it is not a win rate.
Signal days are distinct session dates with trades. Groups can trade on the same
dates, contain the same moves and overlap in time. Summing their trades does not
create a tradable combined portfolio; equal-group and trade-weighted means differ.

For each reported mean range, sample the observed trade-bearing session dates
with replacement, retain each selected day's trade sum and count, divide total
sampled points by sampled trades, repeat 1,000 times. Use the 2.5th/97.5th
percentiles. Seed 20261021 is hashed with the group key (see configuration).
These are historical day-resampled mean ranges, not forecasts of individual
trades. They ignore dependence beyond a day and have no adjustment for searching
many groups and parameters. Do not interpret a range above zero as validated edge.

## Licensed input and reproduction

Input is the same continuous, unadjusted ES minute archive used by the companion
study. SHA-256: 2a794cbeae8f8fc3022d4079e98c32e8d9dc030ba1d1bda2b457aa857f0fa6f9.
Raw range June 6, 2010–September 11, 2026 UTC. Obtain your own licensed input with
the identical documented construction to match these results; the fingerprint is
not a public download or a data license. Contract selection/roll construction and
vendor prices have not been independently rebuilt. Source quality flags are
retained for both models; complete minutes do not mean perfectly reliable prices.

Parquet columns: timestamp_utc (aware UTC minute-start), open/high/low/close
(finite positive OHLC), underlying_contract, roll_transition, is_complete,
quality_state and price_source. Keep complete rows, sort timestamps, reject
duplicates, never fill missing minutes. Contract joins are volume-based upstream;
the input audit records source quality counts, dates, rolls and exclusions.

Tested Python 3.12.14 with the pinned dependencies:

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_LICENSED_ES.parquet --output results --private-cache YOUR_PRIVATE_TEMP_FOLDER
python -B verify.py --private-cache YOUR_PRIVATE_TEMP_FOLDER
python -B verify_mechanics.py
```

The temporary cache contains per-window outcomes and dates and must remain
outside the public study directory. Do not distribute it. Public results contain
only group aggregates, parameter choices, audits and verification records.
The full strict gross-outcome, stop and eligibility matrices must match the
companion study's previously independently reconstructed hashes (12 comparisons).
This verifies continuity with that check; it is not a new independent price audit.
The follow-up verifier separately recounts aggregate cells and development choices
from temporary outcomes, tests selection mechanics, and checks original selected
counts/means against the saved source table. It separately recounts every selected
mean range using the checked one-trade-per-group-per-session property; unselected
candidate intervals are not separately checked. The original saved column name `holdout` is historical
provenance; this article does not claim untouched dates.

`engine.py` and `legacy.py` preserve the companion calculation helpers; the
follow-up calls the documented source, window, history, trade and resampling
functions. Its entry point is `reproduce.py`. `source-selection-summary.csv` is
the safe aggregate projection of the older selection table; no source trades or
vendor price records are included. Approval and publication are separate owner actions.
