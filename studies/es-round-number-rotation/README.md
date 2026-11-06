# Does ES rotate more around 25-, 50- and 100-point prices?

Prepared October 22, 2026. Research-only package; no original vendor records,
indicator exports, raw chats, machine paths or website/card code are included.

## Answer and practical meaning

This attachment shows two-sided movement around ordinary shifted prices as
well as round prices. The raw one-hour median two-sided distance is 7.875 points
for 156 first touches of multiples of 25, versus 7.5 points for 152 halfway-grid
touches. 78/156 round events and 71/152 control events reach at least 8 points
on both sides. These are unmatched, overlapping descriptive events on only 52
previously examined sessions. The 0.375-point difference in medians is not an
estimate of profit or evidence of a dependable round-number effect.

The added same-day/time/recent-range comparison retains just six event pairs
on six sessions for the main halfway grid. Four round and four control events
reach both sides by 8 points. This is too little matched evidence to decide
whether round prices add a special effect. No rotation band or trading rule
is recommended. Sparse matching is a finding; the matching rules were not
relaxed to obtain a larger or more attractive result.

## Source and overlap with the earlier study

The recovered user-supplied CSV has 21,060 minute bars across 52 observed dates,
May 18–July 31, 2026. Every included date has exactly 405 consecutive bars,
09:30 through 16:14 America/New_York. The fixed observation window therefore
ends at 16:15. It is the export's window, including the 15 minutes after 16:00;
it is not an independently constructed exchange calendar or a claim that every
possible trading date appears. No source dates fail this completeness check.

Only time and OHLC columns are used; indicator/volume columns are ignored.
Timestamps must be aware, strictly increasing and unique; OHLC must be finite,
positive, ordered and on 0.25-point ticks. Nothing is forward-filled. UTC elapsed
times and New York clock labels must both have consecutive minutes. The export
has no dated-contract, roll/adjustment or vendor quality fields. Continuous
contract settings and underlying prices have not been independently audited.
Absolute price levels may depend on that unverified construction.

SHA-256: ac031d40130b429d1e500ce4ffa8d91cbf975540db12e52adfc893dfb21e9424.
The fingerprint identifies the input, not a download route or data license.
Obtain your own authorized identical export to reproduce the saved results.

The earlier exploratory report used this same attachment. We recovered its
question and described method, but not its original source program or per-event
log. A fresh implementation matches 27 earlier reported raw aggregates within
their printed rounding. Its class-specific control matching, completed-range
midpoint and recrossing calculations are not reproduced. They are not presented
as checked findings here. There is no untouched date range in this article.

## Exact events and two-sided distance

Let an integer k identify a base price 25*k. Distinct real classes are:

* 100: k divisible by 4.
* 50-only: k divisible by 2 but not 4.
* 25-only: k odd.

They do not double-count: 6000 belongs only to 100, 6050 to 50-only and 6025 to
25-only. These are illustrative prices, not source observations.

Control grids are 25*k + shift, for shifts 6.25, 12.5 and 18.75 points.
The main control is 12.5, halfway between neighboring multiples of 25.
Control class labels inherit k from their base price; they are not themselves
round-number classes. This explicit convention differs from unspecified
class-specific control matching in the old report. All grids get their own
first touch, rather than being measured at the real level's touch time.

For each observed date and each level, find the first minute satisfying
low <= level <= high. A gap between bars without that in-bar range condition
does not count as a touch. The high/low test is a bar-range reference, not proof
that an order could execute at every intervening price. Later touches are ignored.

Exclude the entire touch bar from future extremes, because its high/low ordering
relative to the touch is unknown. For horizon h = 15/30/60/120:

```text
t = index of the first touch bar, counting from 0 at 09:30
future = bars t+1 through t+h, inclusive
require all h future bars inside this same 405-bar date
up = maximum future high - level
down = level - minimum future low
two-sided distance = max(0, min(up, down))
both-sides event at distance d = two-sided distance >= d
```

A touch in the 13:00 bar becomes fully observable at 13:01. Its 60 subsequent
bars start 13:01 through 14:00 and finish at 14:01. A 15:14 touch is the latest
eligible for 60 complete subsequent bars before this export ends at 16:15.
Events without a complete horizon are excluded, rather than shortened or set
to zero. Each horizon has its own eligible-event denominator.

Made-up example: after a 6000 touch, future highs reach 6011 and lows reach 5992.
Distance = min(11, 8) = 8 points. If all future prices remain above 6000, distance
is zero. A large range in the touch bar contributes nothing. This measure records
two future extremes; it does not require repeated crossings, establish their
order, prove a return-to-level probability or model a trade.

## Matching remaining time and recent range

Compute the range of the previous 30 completed bars, excluding the touch bar:
max(high[t-30:t]) - min(low[t-30:t]). A first touch before index 30 cannot use
this within-window history and is ineligible for matching; its raw event remains.
Do not relabel a later touch as the first eligible touch.

For each horizon/control shift/class comparison, candidate real/control pairs
must share the same observed date, same 15-minute touch-time bin anchored at
09:30, and same 5-point prior-range bin. Range bins are [0,5), [5,10), etc.
This gives similar remaining window time (at most 14 minutes apart) and similar
recent movement (less than 5 points apart). It is coarse matching, not exact
control of volatility or all market conditions. The main six pairs are at most
11 minutes and 1.25 prior-range points apart.

Sort all candidate pairs by absolute touch-time difference, absolute prior-range
difference, real base k, control base k, then event indices. Greedily accept the
next pair when neither event has been used in that comparison. Never use future
distance to choose partners. Controls cannot be reused within a comparison.
Pooled and class-specific comparisons are matched separately; they overlap and
must not be added as independent evidence. Alternative shifts are sensitivity
checks on these same dates, not new samples.

The 60-minute pooled main raw counts are 156 real/152 control. The prior-history
requirement leaves 86/82 eligible to be matched, and date/time/range matching
leaves 6 pairs. The +6.25 and +18.75 sensitivities leave 9 and 16 pairs, on 8 and
16 sessions respectively. These sparse results are retained without retuning.

## Statistics, resampling and costs

Mean = sum / event count. Median = middle sorted distance, averaging the two
middle values when even; it can therefore be a half-tick. Quartiles use NumPy's
default linear interpolation at 25% and 75%. Both-side share = qualifying events
/ all eligible events in that row, including zero-distance events.

Paired mean distance difference = average(real distance - control distance).
Paired share difference = 100 * (real qualifying events - control qualifying
events) / pairs, in percentage points. A difference between raw medians is not
the mean of paired differences. Neither estimates an expected trading return.

Saved diagnostic resampling draws trade-free observation dates with replacement,
keeps every matched pair from each selected date, then divides summed paired
differences by sampled pair count. Repeat 2,000 times and use 2.5th/97.5th
percentiles. Seed 20261022 is hashed with horizon/class/shift/measure. Diagnostics
have no search adjustment or preservation of dependence beyond a date. With only
0–16 matched sessions in the main-hour comparisons, resampling can produce
misleadingly precise endpoints. The article does not use these intervals as
formal evidence, does not show a significance gate, and makes no class ranking
from the tiny matched subsets. This caveat applies even when a saved interval
happens to exclude zero. The intervals are not independently reimplemented.

There is no entry/exit, stop, target, position sizing, P&L or cost deduction here.
Costs cannot be subtracted from a two-sided range to create a valid trading
return. A two-sided touch share is not a win rate or an achievable profit rate.

## Reproduce and verify

Tested Python 3.12.14, NumPy 2.3.5 and tzdata 2026.5:

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_AUTHORIZED_EXPORT.csv --output results
python -B verify.py --input YOUR_AUTHORIZED_EXPORT.csv
```

The required CSV columns are time (aware ISO 8601 timestamp), open, high, low,
close. Extra columns are ignored. No vendor records are written to outputs.
raw-summary.csv contains 64 grid/class/horizon aggregates; matched-summary.csv
contains 48 matched comparisons, including zeros. summary.json records audits,
event and matched-identity hashes and the main comparison. verification.json
records actual checks; earlier-reported-checks.json contains safe prior
aggregate claims for the source recount.

An independent CSV/column-array implementation reconstructs all 2,511
event/horizon records and matches the event fingerprint. Independent cell-based
pair selection checks all 48 matched identities. Eleven made-up mechanics tests
pass, and 1,531 numerical comparisons check raw measures, matched counts,
medians, means and matching distances, including 27 older reported aggregates.
Neither matching nor rerunning the same file creates independent future
evidence. Human review and version-specific publication remain separate.
