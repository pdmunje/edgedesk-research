# Did very weak stock participation precede an ES rebound?

Fresh calculation and independent checks: October 16, 2026. This is an exploratory recheck of closing 50/200-day breadth washouts, not an intraday recovery study or validated trading rule. The original source narrative is a lead; its raw calculation files were not recovered. The original five input attachments were recovered and freshly read. The primary 166-day result and its rounded horizon means reproduce that narrative.

## Licensed inputs and reproduction

Use Python 3.12 (checked with 3.12.14):

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /your/licensed/csv/folder --output output
python -B verify.py --input-dir /your/licensed/csv/folder --summary output/summary.json --output output/verification.json
```

Provide these five user-supplied TradingView chart exports in that folder. No original vendor data, raw chats, market-event prices, private application code or machine-specific paths are distributed.

| Required file | Contents | SHA-256 |
|---|---|---|
| CME_MINI_ES1!, 1D_c578e.csv | Daily continuous ES chart OHLC and four embedded breadth closing columns | 44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4 |
| INDEX_S5TH, D_0f94a.csv | Daily breadth OHLC, percent above 200-day average | 2f89dbf2b120291b69cf3b116df371fe1eec1ea5e73f47b6c799e1af34a50289 |
| INDEX_S5FI, D_96a6d.csv | Daily breadth OHLC, percent above 50-day average | 25910ae25f8c7525351f88394580414ceab3c00c488267d414609cbd48af8c84 |
| INDEX_S5TW, D_dc629.csv | Daily breadth OHLC, percent above 20-day average | 84d372d91bee78ba3aa6944e95f4e5a9eea91c80ef8e8587bf83b98af6bb4825 |
| INDEX_S5FD, D_905a5.csv | Daily breadth OHLC, percent above 5-day average | 05377c278f8c6cc8d734a37ca1405ae77f9ced9d4d28ca821d54c3427f7b0c1f |

All files contain ordered unique `time` dates in YYYY-MM-DD format and `open,high,low,close`. ES also contains column names of the form `S&P 500 Stocks Above 200-Day Average · INDEX: close` (likewise 50, 20, 5). Breadth closing values must be finite and within 0–100. ES OHLC must be finite, positive and range-consistent. This study uses breadth close only; its intraday OHLC is not used to generate a signal.

The ES source has 7,351 daily rows, September 9, 1997–October 2, 2026. The final October 2 row was developing when exported, according to the original research record. Freeze the last complete date at October 1, 2026 and exclude October 2 from all entries and exits. Do not treat the final saved developing bar as completed just because today's date is later.

Breadth source lengths: 5,094 rows (200-day), 4,992 each (50/20-day), 2,451 (5-day). They begin at different dates. Use the common five-file date intersection, January 3, 2017–October 1, 2026, giving 2,451 signal dates, to match the prior research universe rather than extend the sample selectively. Available external breadth closes match the ES file's embedded values: 5,031 + 4,974 + 4,974 + 2,451 = 17,430 matched pairs. Earlier sparse breadth history is outside the common study interval.

These are continuous futures chart prices, with no dated-contract, roll or adjustment metadata. We cannot identify or remove cross-contract returns or verify the adjustment convention from these files. Results are chart-price changes, not confirmed executable-contract returns. Historical constituent membership, the provider's eligible-stock denominator, publication latency and revisions are not independently reconstructed.

## Signal definitions

Breadth is the provider's percentage of S&P 500 stocks above the indicated individual-stock moving average. In conceptual form: 100 × eligible stocks above average / provider's eligible stocks. A reading of 30 means 30 percent, not a 30-percent fall or a 30-point ES decline. The provider's stock histories and average calculations are accepted inputs, not recomputed here.

Primary condition: closing 200-day breadth <= 30. Threshold includes exactly 30. It is known only after the daily breadth observation completes. For context, calculate all closing thresholds 10, 20, 30 and 40 for both 200-day and 50-day breadth, at horizons 1, 3, 5 and 10 ES source sessions: 32 threshold/horizon combinations. These neighboring thresholds are an explicit exploratory comparison, not a claim that this exact grid was frozen before the original exploration. All results are included, not only the most favorable threshold. Intraday recovery and index-new-high conditions are separate queued studies.

## Timing and forward change

Construct the ES calendar from the full ES file through October 1, 2026, BEFORE restricting signal dates to the common breadth intersection. Do not shift only the intersection: that can skip an observed futures session without a matching breadth record.

For a signal on full ES source row i:

* Entry reference = opening price of row i+1.
* For horizon h, exit reference = closing price of row i+h.
* Gross chart-price change (%) = 100 × (exit / entry − 1).
* Illustrative one-point-adjusted change (%) = 100 × (exit − entry − 1) / entry.

One-session horizon therefore enters the next source row's open and exits that same row's close. Ten sessions enter next row's open and exit the tenth later row's close. They are observed ES source sessions, not ten calendar days. The input has date labels, not independently audited release timestamps; next-session entry assumes the completed breadth reading was available before that next opening reference. No actual order, holiday/session-boundary timestamp, spread, funding, roll trade, margin or account-value model is verified.

If the required entry or exit lies beyond the last complete ES row, that outcome is unavailable and excluded from its horizon denominator, never zero. For all 2,451 common signal dates, available baseline counts are 2,450, 2,448, 2,446 and 2,441 at horizons 1, 3, 5 and 10. All 166 primary-condition dates have all four outcomes; primary signal dates run December 17, 2018–April 21, 2025.

## Four ways to count the same condition

1. **Every qualifying day:** a new hypothetical window after every breadth close <= threshold. Windows can overlap substantially. The primary condition has 166 days.
2. **First day of each consecutive signal run:** keep a qualifying common-date observation only if the previous common-date observation did not qualify, or it is the first observation in the sample. Consecutive means consecutive available common breadth dates, not consecutive calendar days. The primary condition has 15 such runs. Separate runs can still have overlapping forward windows or share market conditions; they are not proven independent economic episodes.
3. **Nonoverlapping windows for horizon h:** scan qualifying dates chronologically, keep the first, and then accept another only when its full ES source-row index is at least h beyond the last accepted index. The first trade enters row i+1 and exits row i+h close; a new signal at row i+h can enter afterward at row i+h+1. The 10-session primary count is 23. Repeated windows within a prolonged selloff can remain correlated even without overlap.
4. **Five-session spacing:** same greedy procedure with gap 5 regardless of outcome horizon. This reproduces the prior 40-observation, ten-session mean of about +2.35%, but ten-session windows can still overlap when only five sessions separate signals. Do not call this 40 independent trades or independent selloffs.

Select spacing from dates with a complete outcome for that horizon; first-run starts are defined on all qualifying observations and then exclude unavailable outcomes. No unavailable future observation is silently converted to no-signal.

The counting policies define different entry/reentry rules. Their different means do not identify a cause by themselves, and no most favorable policy is selected for live trading.

## Baselines, units and statistics

The ordinary baseline uses every common-date observation with a complete horizon outcome. All means weight each event equally; they are not a portfolio or compounded account return. Positive count = gross chart-price change > 0; flat observations stay in the denominator and are not positive. Median is the middle sorted change (mean of two middle changes if even n). Extremes are individual forward windows, not account drawdown.

For a calendar-matched descriptive benchmark, take all OTHER common signal-date observations with the same calendar year and weekday as a qualifying date, and complete outcome at that horizon. Their average is that event's reference. Other qualifying days can be included; it is not an exclusively non-signal control. Exclude the event itself. Average these references across the selected signal events. Excess = mean(signal change − matched reference), in percentage points. This matching uses the observed sample for comparison and is not a real-time trading input. It controls neither volatility nor all market conditions, and does not establish causality.

For 200-day breadth close <=30, ten-session gross mean is +2.663019% across 166 dates; 125/166 are positive. The unconditional baseline is +0.555601%. The matched mean is +0.025879%, reflecting the concentration of signals in particular years; it is not the same as the unconditional baseline. First-run-day ten-session mean is +0.541606% across 15; nonoverlapping mean is +1.360838% across 23. First-run-day five-session mean is −0.159473%. Those weaker results are retained.

Primary earlier/later groups split at January 1, 2022, following the source's broad period comparison. Both periods were already examined, not untouched holdouts. One-point adjustment is an assumed round-trip chart-price cost, not a measured fee or a solution to unknown roll adjustments. No statistical confidence, significance, multiple-search correction or forecast probability is claimed. The earlier source mentioned stronger inferential claims; those are not accepted or reproduced as part of this focused audit.

## Outputs and verification

`results/summary.json`: source fingerprints, validation, baselines, all 32 threshold/horizon combinations under four counting policies (128 rows), primary period comparisons, formulas and limitations.

`results/threshold_summary.csv`: the same 128 aggregate result rows with counts, average/median, positive counts/percentages, one-point scenario, matched benchmark and extremes. It contains summarized research results, not original source prices or daily breadth records.

`results/verification.json`: actual check record. `verify.py` uses a separate standard-library CSV reader, full ES row calendar, forward-price arithmetic, leave-one-out peers, first-run and spacing selection. It checks all individual common-date forward changes, all 128 aggregate rows, baseline and period statistics. Nine invented tests check next-open arithmetic, cost conversion, exact nonoverlap spacing, missing outcomes, threshold equality, first-of-run counting, strict positive counts and leave-one-out means. Source files are fingerprinted before/after; vendor histories and timestamp/contract assumptions are not independently certified.

October 16, 2026: original attachments recovered, fresh portable calculation, independent recount, old rounded primary result reproduced, full ES calendar retained, new matched baseline and stricter episode/overlap checks disclosed. This is a research draft; human publication approval is separate from calculation checks.
