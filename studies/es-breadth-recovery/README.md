# After weak stock participation, did partial recovery beat a strong rebound?

Checked October 16, 2026. This rechecks an earlier Backtesting ES research lead. These dates and cutoffs were previously explored; they are not an untouched test. The original five chart attachments were recovered; old calculation files were not. Primary recovery counts and rounded means reproduce. One older 50-day five-spacing mean differs by 0.01 percentage point, explicitly retained below.

## Reproduce

Use Python 3.12 (checked with 3.12.14) and the pinned dependencies:

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /your/licensed/input/folder
python -B verify.py --input-dir /your/licensed/input/folder
```

Default calculation outputs and verification use this folder's `results/`. An optional `--output` can place new calculations elsewhere; the verifier intentionally checks the bundled `results/` version, so use the default when checking a rerun. Only aggregate summaries are written. Original vendor bars, event prices, raw chats, private application code and machine-specific paths are excluded.

## Required licensed input files

| File | Meaning | SHA-256 |
|---|---|---|
| CME_MINI_ES1!, 1D_c578e.csv | Continuous daily ES | 44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4 |
| INDEX_S5TH, D_0f94a.csv | Daily stock breadth 200-day average | 2f89dbf2b120291b69cf3b116df371fe1eec1ea5e73f47b6c799e1af34a50289 |
| INDEX_S5FI, D_96a6d.csv | Daily stock breadth 50-day average | 25910ae25f8c7525351f88394580414ceab3c00c488267d414609cbd48af8c84 |
| INDEX_S5TW, D_dc629.csv | Daily stock breadth 20-day average | 84d372d91bee78ba3aa6944e95f4e5a9eea91c80ef8e8587bf83b98af6bb4825 |
| INDEX_S5FD, D_905a5.csv | Daily stock breadth 5-day average | 05377c278f8c6cc8d734a37ca1405ae77f9ced9d4d28ca821d54c3427f7b0c1f |

All files require ordered, unique `time` dates in YYYY-MM-DD format and `open,high,low,close`. The ES file additionally contains the four embedded columns named `S&P 500 Stocks Above 200-Day Average · INDEX: close` (likewise 50, 20, 5). ES prices must be finite, positive and range-consistent. All breadth closes must be finite 0–100; analyzed 200/50-day breadth OHLC must also be finite 0–100 with low <= open/close <= high. Invalid records fail the calculation.

ES has 7,351 rows from September 9, 1997 to October 2, 2026. Freeze completion at October 1, 2026: the saved October 2 row was developing at export and must not become completed merely because today's date is later. Breadth files contain 5,094 (200), 4,992 each (50/20), and 2,451 (5) rows; all four intersect ES on 2,451 dates from January 3, 2017 to October 1, 2026. Requiring every source retains the source study's universe. External/embedded closes match across 17,430 available pairs. Earlier sparse breadth history is outside this universe.

## Exact calculation and timing

Breadth conceptually equals 100 times eligible stocks above their individual-stock moving average divided by provider-eligible stocks. We accept provider values rather than rebuild constituent histories or averages. The primary daily low is 200-day breadth <=40. Secondary conditions are 50-day breadth daily low <=30 and 200-day daily low <=30. They use lows, not the closing thresholds studied in the related washout article.

Recovery = (breadth close - breadth low) / (breadth high - breadth low). A zero high-low range is undefined, not zero recovery. Groups: poor [0,.25]; middle (.25,.40); partial [.40,.75); strong [.75,1]. These exhaust valid nonzero-range candles; exactly .75 is strong. Both analyzed breadth series have five zero-range days in the common universe. Primary low<=40 has one; 200 low<=30 also has one; 50 low<=30 has none. A zero-range candle remains inside a qualifying low-breadth spell.

Made-up example: breadth low30/high50/close42 yields (42-30)/(50-30)=.60, partial. Close45 yields .75, strong. Low<=40 is satisfied in both cases. Low=high=close30 gives undefined recovery.

Construct the full ES calendar through October 1 BEFORE joining breadth. For signal source row i, entry is ES open at i+1, exit at i+h close for h in 1,3,5,10. Gross change (%) = 100*(exit/entry-1). Sessions are full ES source observations, not calendar days or filtered breadth rows. Missing end outcomes are excluded per horizon, never zero. All-date baseline denominators: 2450,2448,2446,2441. Date labels do not verify release time; this next-open reference assumes completed breadth was available by that open. No actual fill is established.

## Counting and comparisons

For each of 3 low-breadth conditions x 4 recovery groups x 4 horizons x 4 counting policies, retain all 192 aggregate rows:

1. Every qualifying recovery day: forward windows may overlap.
2. First qualifying date in each consecutive low-breadth spell, separately per group. Spell starts when low first meets threshold and ends when low exceeds it on successive common dates. No future bottom confirmation. Within each horizon's measurable dates, keep the earliest date per spell/group. Partial and strong can occur in the same spell on different days. This is not a paired same-date comparison. A later reappearance of a group does not reset its spell.
3. Nonoverlapping windows: greedily keep first qualifying measurable date; accept another only when its full ES source row is >= last accepted row + h. With h=10, signal row0 holds rows1-10; row10 can signal for entry row11. Spacing is separate by group; across-group windows can overlap. Same-selloff windows can remain correlated.
4. Five-session spacing: same greedy rule with gap5. Ten-session outcomes can still overlap; these are not independent selloffs.

Means weight windows equally; positive means gross change strictly >0, with flats retained in denominator. Median is the middle sorted outcome (average of middle two for even n). Min/max describe individual windows, not account drawdown. All-date baseline uses every common date with an outcome; all-washout baseline additionally includes qualifying zero-range days if their outcomes are complete. First/last signal dates refer only to measured windows in each summary.

Calendar benchmark: for each event, average all other complete common-date outcomes with the same signal year and weekday. Other qualifying days may remain. Average these event-specific references. Difference = mean(event change - reference), in percentage points, using unrounded values. It is an observed-sample descriptive reference, not a live feature or volatility/causal control.

One-point scenario = 100*(exit-entry-1)/entry, one assumed point for the entire round trip. It is not actual commission/slippage and does not solve roll adjustments. Earlier/later groups split at 2022-01-01; both were already explored, not holdouts.

## Findings and limits

Primary low<=40 gives 358 days in 30 spells: one undefined recovery; 116 poor,37 middle,83 partial,121 strong dates. One final partial date lacks outcomes, leaving82. Ten-session means: partial +2.262554%,64/82 positive; strong +0.368980%,81/121 positive. All-date baseline +0.555601%; all measured weak-breadth dates +1.394059%. First partial-per-spell gives21 outcomes,+2.557687%,16/21 positive; first strong gives26,-0.612427%,15/26 positive. Only21 of22 spells containing partial recovery have a measurable first outcome. Nonoverlap gives35 partial,+2.197737%; see exact JSON rather than this rounded description.

The older 200-day partial five-spacing means reproduce (+2.46%,47 observations at low<=40; +3.17%,24 at low<=30). For 50-day low<=30 partial, ten-session five-spacing mean is +2.50%,44 observations,34 positive; old narrative said +2.51%. No old code is available to resolve the 0.01-percentage-point difference. Other raw rounded recovery means reproduce. Counts must be reported per horizon: e.g. 72 50-day partial signal dates yield only71 ten-session outcomes.

Continuous ES chart prices lack dated-contract, roll and adjustment metadata. Cross-contract changes cannot be removed or price adjustments certified. These are chart-price changes, not verified executable-contract P&L. Historical constituent membership, provider revisions, exact release timestamps and order execution are not audited. No stops, account sizing, margin, funding, compound equity or roll policy is modeled. No confidence interval, multiple-search-adjusted significance or future probability is asserted. Overlapping groups, neighboring thresholds, earlier/later splits and related washout/new-high studies share inputs and are not independent confirmation.

## Verification and files

`analysis-config.json` records source cutoffs and policies before this rerun; it is not a new preregistration. `reproduce.py` computes recovery groups/spells and aggregate results; `breadth_base.py` validates shared inputs and calculates full-ES-calendar outcomes, spacing, costs and calendar references. `verify.py` separately parses raw CSV/date records and recounts forward arithmetic and groups using Python's csv/statistics logic. It checks individual recovery values/groups, forward changes, all192 result rows and CSV values, baseline/period/reference/cost summaries and all source fingerprints. Eight made-up checks cover boundaries/undefined range, missing breadth dates, invalid candles, repeated groups within a spell, spacing equality, missing/flat outcomes and round-trip cost. Actual record: 23,237 independent value comparisons passed. This verifies implementation against the supplied inputs, not provider correctness or forecast validity.

`results/summary.json` holds fingerprints, input quality, all results and period comparisons. `results/recovery_summary.csv` is the same192 aggregate rows with condition/group/horizon/policy, count, mean/median, positive count/rate, cost scenario, calendar reference/difference, extremes and measured first/last dates. `results/verification.json` records actual checks and the unresolved small prior-claim discrepancy. No daily event-price output or original vendor data is distributed.
