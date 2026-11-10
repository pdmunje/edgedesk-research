# Do repeated daily declines precede a stronger next ES day?

Prepared November 1, 2026. Fresh descriptive reconstruction on a previously
explored owner-provided daily file. No unused later dates, executed trades,
confirmed discovery, original full-search correction or account result is claimed.

## Main finding and the two denominators

For predictors dated 2010 onward, four lower close-to-close moves precede 91 green
and 57 red targets, plus one exact-doji target. Color is 91 / 148 = 61.4865%, versus
the no-condition baseline 2,267 / 4,119 = 55.0376%. That is +6.4489 percentage points,
not a trading return. All 149 targets enter price-change averages, including the
doji. Mean next open-to-close change is +12.994966 ES points; mean predictor-close
to target-close change is +13.149329, with a +0.154362 mean opening change.

Four lower highs instead have 131 / 221 = 59.2760% green and 224 all-target price
outcomes; four red candles have 81 / 140 = 57.8571% green and 144 all-target
outcomes. Equal phrase length does not make these the same condition. Every
length 2, 3, 4 and 5 for all three definitions is retained, including weak results.

## Authorized input and source dates

Provide the identical authorized CSV with time, open, high, low, close columns.
Extra columns such as Volume do not participate. Prices are ES points; time is
a date-only ISO vendor daily label. Require increasing unique dates, positive
finite prices and low <= open/close <= high. The original file has 7,285 rows,
September 9, 1997 through June 30, 2026. Source SHA-256:

aa50dad895c5698ae35e24333cf093b682736a4d8477e53563ca7607ef7037eb

A hash identifies the file, not a license or a downloadable dataset. Original
vendor rows are excluded. The recovered attachment and another saved source
copy have identical hashes/endpoints; they are one dataset, not new validation.

All recorded dates are weekdays, but no independent exchange calendar or expected
session coverage is established. Use adjacent stored rows, including across
weekends/holidays; fill no missing dates or prices. Four rows have a saved OHLC
value outside the usual quarter-point grid and are preserved, not rounded.
Continuous-contract construction, roll settings, pre-launch history and exact
aggregation/session endpoints remain unverified. Date labels do not establish
intraday completion, order availability or actual fill timestamps.

## Completed conditions and period rules

For predictor row t, length k in {2,3,4,5}:

    lower_closes: close[j] < close[j-1] for j=t-k+1,...,t
    lower_highs:  high[j] < high[j-1] for j=t-k+1,...,t
    red_candles:  close[j] < open[j] for j=t-k+1,...,t

The first two need k comparisons and k+1 stored rows; red candles need k rows.
All inequalities are strict: a tie breaks the relevant sequence. A predictor doji
breaks a red sequence. These are at-least-k rules, not exactly-k completed runs.
Every qualifying predictor counts; do not wait for the streak to finish or keep
only its first signal. Longer streaks also belong to shorter-length groups.
Families, lengths and nearby observations overlap; their counts are not additive
independent evidence.

The target is the immediately following stored daily row. The final source row
has no target: 7,284 adjacent pairs remain. Select periods by predictor vendor
date >= 1997-09-09, 2010-01-01 or 2020-01-01. Earlier rows still supply legitimate
lookback history. A year-boundary target belongs to its predictor's period.
Exclude unavailable initial histories from a pattern AND its baseline pool.
The full-history pattern baseline can therefore differ slightly from the
no-condition baseline; primary/recent histories are all available.

## Exact measures, units and exclusions

    green = target close > target open
    red = target close < target open
    doji = target close == target open exactly
    color_n = green count + red count
    green_pct = 100 * green count / color_n
    baseline_green_pct = 100 * eligible green count / eligible non-doji count
    green_change_pp = green_pct - baseline_green_pct

    all_n = green count + red count + doji count
    body_points = target close - target open
    gap_points = target open - predictor close
    close_change_points = target close - predictor close
    close_change_points = gap_points + body_points, for each target

    body_pct = 100 * (target close / target open - 1)
    close_change_pct = 100 * (target close / predictor close - 1)

The percent fields are price ratios, not sized account returns. Red share is
100 minus green share on the same non-doji denominator. All point/percentage
means and medians use all_n, including exact dojis. Source-full target dojis = 89.
Primary no-condition counts: 4,156 all targets, 4,119 non-doji, 2,267 green,
1,852 red, 37 doji. Never reuse the color denominator for price changes.

A mean sums all corresponding values and divides by all_n. A median is the middle
sorted value, averaging the two middle values for an even count. Four-lower-close
primary medians are +6.25 body points and +7.00 close-change points. Means obey
the body/gap identity; medians do not generally add. One ES point is a price unit;
the usual tick is 0.25 points. No dollar-profit conversion is made.

Invented example, not source observations: predictor close 5,000; target open
4,990 and close 4,995. The candle is green, body +5 points, opening change -10,
close-change -5. If target open/close both equal 4,990, exclude it from color
shares but retain its zero body and -10 close-change in price averages.

## Search, archive and validation limits

There are 12 listed patterns and 39 summary rows = three overlapping date ranges
* (12 patterns plus baseline). Recent/primary/full periods share the same endpoint;
the recent dates were inspected in earlier research. They are not independent
replications or untouched validation. Raw point sizes can change with price and
volatility regimes, which is why percentage-change summaries are also retained.
No later daily dates are included or invented here.

The saved workbook describes a much broader screen of 215 names / 212 distinct
selections. Its full original executable search, selection history and inference
were not rerun/certified. Do not call a favorable row a new discovery or apply a
shortlist-only correction as if it covered all past choices. No new p-values,
confidence intervals or significance label is computed here. Dependence, repeated
searching and reused dates remain limitations.

Eleven current definitions have corresponding archived rows. The recorded archive
check compares 33 period-specific rows on seven fields: color denominator, green,
red, doji, mean/median close-change points and mean close-change percentage. All
231 comparisons agree. Five lower-high moves is an explicit extension in this
recheck; no matching row exists in the old catalog. The private read-only source
workbook hash is recorded in archive-reconciliation.json, not the original file.
This archive check is a recorded limited reconciliation, not a substitute for the
independent raw-input verifier or a certified broad-search inference.

## Chart changes are not executed strategy returns

The daily label does not verify when the predictor finalized or a first executable
order could arrive. The next saved open is an observed chart reference, not a
verified post-signal fill. A predictor-close change includes an opening change
that an entry afterward may not capture.

No positions, entry/exit orders, stops, targets, slippage, commissions, execution
gaps, overlapping positions, sizing, account drawdown or annual return are modeled.
Chart changes are before costs; that does not assume a cost-free trading strategy.
A separate fixed-rule execution study and genuinely unused later data are still
needed before claiming trading value.

## Reproduce and verify

    python -B reproduce.py --input YOUR_AUTHORIZED_EXPORT.csv
    python -B verify.py --input YOUR_AUTHORIZED_EXPORT.csv

Tested Python 3.12.14, standard library only; no package install required.

- config.json: exact source hash, cutoffs, all families/lengths and denominator rules.
- reproduce.py: strict price/date checks, completed-window flags and summaries.
- verify.py: own Decimal parser, cumulative streak arrays and summary arithmetic.
  It agrees on 975 numeric/date/identity/fingerprint checks across 39 rows. Nine
  invented boundary assertions additionally exercise production mechanics. No
  production loader/window loop/full-file summarizer is reused by the main check.
- results/summary.csv: every result, color/all-target counts, baseline counts,
  green percentage/change, five mean/median measurements, matching-date bounds
  and ordered predictor-index fingerprints. No individual price rows are stored.
- results/audit.json: source coverage, exclusions and scope limitations.
- results/verification.json: actual independent check result.
- results/archive-reconciliation.json: limited read-only archive check described above.

Checks establish agreement on these stated historical calculations, not vendor
truth, statistical discovery, real fills or future returns. Keep original vendor
data, raw chats, individual target observations, account details, private machine
paths, credentials and website/card source outside this research-only directory.
The owner reviews the exact article, files and matching card before publication.
