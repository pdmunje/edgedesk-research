# After a large weekly fall in SKEW, did ES rise?

Checked October 16, 2026. This is a focused fresh recheck of an earlier weekly SKEW research lead. Original source evidence and two recovered inputs were read; old calculation files were not recovered. The fixed five-point means, four/eight-week spacing and period results reproduce. The older standardized-change claim does not reproduce exactly under either disclosed history definition. These dates and thresholds were already explored; this is not untouched validation or a verified trading strategy.

## Reproduce

Use Python 3.12 (checked with 3.12.14):

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /your/licensed/input/folder
python -B verify.py --input-dir /your/licensed/input/folder
```

Results and verification are written under this study's `results/`. Only aggregate outputs are saved. No original vendor bars, daily event prices, private machine paths, credentials, private application code or raw chats are distributed.

## Required input files and schema

| File | Meaning | SHA-256 |
|---|---|---|
| CME_MINI_ES1!, 1D_c578e.csv | Daily continuous ES chart prices | 44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4 |
| CBOE_DLY_SKEW, 1W_a7232.csv | Weekly SKEW chart open/high/low/close | 3758569910b82712d2d7d97732ed2e9a7f718de77dcd637ff933c9d3bb172383 |

Both need ordered unique `time` dates in YYYY-MM-DD format and finite positive `open,high,low,close` with low<=open/close<=high. Extra columns are ignored. Source weekly labels can be Monday, Tuesday or Wednesday. Map to calendar Monday; never invent an earlier SKEW opening value. Weekly open/close remain the provider bar's first/final values. There are133 holiday-shifted labels and three absent calendar weeks: 2000-09-25,2014-03-17,2014-04-07.

SKEW source has1,915 rows from January1,1990–September28,2026. Exclude the final developing week. ES has7,351 rows from September9,1997–October2,2026. Its last week is incomplete; exclude all five ES rows in the week beginning September28, including the developing final daily bar. Freeze completion at the week beginning September21 (ending September25). Do not complete saved developing bars because today's date is later. Common signal universe has1,513 weeks, September8,1997–September21,2026. The first ES week is partial, but the SKEW signal uses its own full weekly bar and outcomes start the following week.

## Exact fixed and normalized signals

SKEW is an index derived from S&P500 options; use provider index values rather than reconstruct options. [Cboe's January2011 introductory paper](https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf) explains its method and historical series. The early history is reconstructed, not proof the index was available to trade in real time then. The export contains no historical publication/revision archive.

Change in SKEW points = current weekly close minus current weekly open. Primary signal: change<=-5; exactly-5 qualifies. This is not close-versus-previous-close and not a percentage change. Made-up example: open150/close145 gives-5 points; close145.01 gives-4.99 and fails. Retain all source cutoffs -2,-3,-4,-5,-6,-7,-8.

Main normalized definition: on a regular Monday weekly calendar, use exactly the PREVIOUS104 calendar-week changes, excluding current. Require all104 actual observations. Earlier mean=sum/104; sample standard deviation=sqrt(sum((change-mean)^2)/103), ddof1. Standardized change=(current change-earlier mean)/earlier sd; signal<=-1.5. Missing history or sd0 makes it undefined, not a signal. Made-up mean0/sd4/current-6 gives-1.5. Missing historical weeks reduce eligible common signal weeks to1,303. Compare normalized results with this eligible baseline.

History audit also uses the previous104 actually reported observations, which may cross missing calendar weeks. It has1,513 eligible common weeks. This variant was added to audit the older unspecified gap handling, not selected by outcome. Calendar history gives89 signals with four-week mean+1.970899%; reported-observation history gives111/+1.851728%. The source claimed101/+1.80%. Gaps explain differences between fresh definitions but do not establish the reason for the old101-event selection; old code is unavailable and the remaining discrepancy is unresolved.

## Outcome timing and counts

Use Monday–Sunday calendar weeks. For signal week w, entry is the first observed ES source open in w+1; h-week exit is the last observed ES close in w+h for h=1,2,4,8,13. Require every holding week to exist and be completed. Gross chart change%=100*(exit/entry-1). Week horizons are not exactly5*h sessions because of holidays. Build the full ES weekly calendar before joining/filtering SKEW; absent SKEW future bars do not shift an ES holding period. All-week horizon denominators:1512,1511,1509,1505,1500. Missing outcomes are excluded per horizon, never zero.

Made-up timing: signal week September7 enters first ES open in week September14; four-week exit is last ES close in week October5. Entry5000/exit5100 gives+2%. If the next week has no Monday source bar but begins Tuesday, use Tuesday's observed open. Availability before that opening reference is assumed, not timestamp-audited; early reconstructed history prevents a historical executable-rule claim.

## Counting policies and benchmarks

Seven fixed cutoffs plus one calendar-history normalized signal x five horizons x five counting policies=200 aggregate rows. The reported-history audit adds five horizon summaries in JSON. The source's broader searches over levels, candle geometry, barriers, controls and combinations were not fully documented/recovered and are not reconstructed or statistically validated here.

Every qualifying week can produce overlapping holdings. First consecutive qualifying week requires the prior calendar week not to have been a qualifying observed signal; missing weeks interrupt runs. The primary155 weeks form132 runs. Define run starts on all signals, then remove incomplete outcomes at the selected horizon. Nonoverlap greedily keeps the first measurable signal then accepts another only if its signal calendar-week index is>=last+h. Four/eight-week spacing uses fixed gaps regardless of horizon. Four-spacing equals nonoverlap for four-week holdings but still overlaps eight/thirteen-week holdings. First runs, nonoverlap windows and spaced signals need not be independent economic episodes.

All means weight windows equally. Positive means gross change>0, with flat outcomes retained in denominator. Median is middle sorted value (average of middle two for even n). Extremes are individual windows, not account drawdown. Ordinary baseline uses all common observed signal weeks with a complete horizon. Normalized eligible baseline also requires its full history.

For each event, same-year reference=mean change of all OTHER common signal weeks in the same signal year with complete horizon, possibly including other signals. Matched mean=average of these per-event references. Difference=mean(event minus reference), in percentage points from unrounded values. It is an observed-sample descriptive calendar comparison, not a live input, volatility match, causal control or exact entry-weekday match. Holiday entries can have different weekdays.

Illustrative one-point cost%=100*(exit-entry-1)/entry, one point assumed for the whole long entry/exit round trip, not each side. This is not measured fees/slippage and does not fix roll adjustments. Earlier/later periods are1997–2009,2010–2019,2020–2026, all previously explored, not untouched tests.

## Findings and remaining limits

Fixed primary has155 four-week windows from signal weeks February2,1998–August3,2026: mean+1.758606%,114/155 positive,median+1.826141%,worst-11.172432%. Baseline has1509 windows,+0.683186%,954 positive. Year-matched mean+0.940675%,so excess+0.817931 percentage points rather than the unconditional+1.075419. Nonoverlap gives110,+1.939661%,82 positive; eight-spacing gives79,+2.365154%,61 positive. Eight/thirteen-week all-signal counts are154/153, not155. Fixed cutoff results weaken at more severe declines; -8 gives only68 four-week windows,+0.88% approximately. No most favorable cutoff is selected as a live rule.

ES is continuous chart data without dated-contract, roll or adjustment metadata. Cross-contract changes cannot be removed and adjustments cannot be certified. These are chart-price changes, not verified executable-contract P&L. Reconstructed early SKEW history, unavailable publication/revision records, assumed availability and unknown actual fills prevent real-time execution claims. No stops, position sizing, margin, funding, roll policy or compounded account return is modeled. Statistical controls, significance, confidence intervals, barrier-first claims and broader earlier search adjustments are unverified and not claimed. Related SKEW-range/breadth articles can share dates and outcomes, so are not independent confirmation. No current trade direction or future probability is recommended.

## Files and verification

`analysis-config.json` records choices; `reproduce.py` validates/alines weeks, computes history-excluding normalization, outcomes, methods and summaries; `verify.py` independently parses CSV/date records and uses Python statistics arithmetic to recount histories, returns, spacing, periods and benchmarks. Nine made-up checks cover holiday labels, next-week opens, current exclusion, sample sd, missing/zero-variability history, cutoffs, run gaps, spacing, missing/flat outcomes and cost arithmetic. Actual verification: 13,923 value comparisons, all200 aggregate rows and source fingerprints passed. This checks arithmetic against inputs, not forecast validity.

`results/summary.json` holds checks, fingerprints, all results/baselines/periods and both normalization histories. `results/weekly_change_summary.csv` contains200 aggregate rows with condition, horizon, policy, event count, mean/median, positive count/rate, cost scenario, same-year reference/difference, extremes and measured first/last signal weeks. `results/verification.json` records actual checks and the unresolved normalized source claim. No raw bars or event-price rows are distributed.
