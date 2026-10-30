# At new ES highs, did breadth warn of a pullback?

Freshly checked October 16, 2026. Original research conversation and five recovered daily inputs were read; old calculation files were not recovered. The 55-event strong-breadth/high means and 30-event next-session five-spacing result reproduce. Some old recent-confirmation percentages do not reproduce under the explicit complete-history and recent-window rules below. This is previously explored research, not untouched validation or an executable strategy.

## Reproduce

Use Python 3.12 (checked with 3.12.14) and the pinned dependencies:

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /your/licensed/input/folder
python -B verify.py --input-dir /your/licensed/input/folder
```

Outputs are written to this study's `results/` folder; the verifier checks that exact folder. Only aggregate outputs are saved. No original vendor data, daily event prices, private machine paths, private application code or raw conversations are included.

## Required licensed source files

| Required file | Contents | SHA-256 |
|---|---|---|
| CME_MINI_ES1!, 1D_c578e.csv | Daily continuous ES chart OHLC and four embedded breadth closing columns | 44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4 |
| INDEX_S5TH, D_0f94a.csv | Daily breadth OHLC, percent above 200-day average | 2f89dbf2b120291b69cf3b116df371fe1eec1ea5e73f47b6c799e1af34a50289 |
| INDEX_S5FI, D_96a6d.csv | Daily breadth OHLC, percent above 50-day average | 25910ae25f8c7525351f88394580414ceab3c00c488267d414609cbd48af8c84 |
| INDEX_S5TW, D_dc629.csv | Daily breadth OHLC, percent above 20-day average | 84d372d91bee78ba3aa6944e95f4e5a9eea91c80ef8e8587bf83b98af6bb4825 |
| INDEX_S5FD, D_905a5.csv | Daily breadth OHLC, percent above 5-day average | 05377c278f8c6cc8d734a37ca1405ae77f9ced9d4d28ca821d54c3427f7b0c1f |


All files need ordered unique `time` values in YYYY-MM-DD format and daily `open,high,low,close`. ES additionally needs the embedded closing breadth columns named `S&P 500 Stocks Above 200-Day Average · INDEX: close` (likewise 50,20,5). Breadth closes must be finite 0–100. ES OHLC must be finite, positive and range-consistent. Only closing breadth is used, not breadth intraday ranges.

ES has 7,351 rows from September 9, 1997 through October 2, 2026; exclude its final developing October 2 row and freeze completion at October 1. There are 7,350 ES source rows for the forward calendar. Breadth source lengths are 5,094 (200-day), 4,992 each (50/20), 2,451 (5). Shared five-file universe: 2,451 dates, January 3, 2017–October 1, 2026. Earlier available rows are used to initialize rolling windows before joining the shared universe. External/embedded breadth closes agree on 17,430 available pairs. No missing source records are filled.

## Exact signals and history eligibility

Breadth conceptually equals 100 times eligible stocks above their individual-stock moving average divided by provider-eligible stocks. Individual stocks, membership and averages are accepted provider inputs, not reconstructed. There are four closing series, above 5/20/50/200-day stock averages. Their equal-weight mean = (b5+b20+b50+b200)/4. It is not the percentage simultaneously above every average, and mean>=80 does not require every series>=80.

For L=20,63,252, ES high means today's close >= maximum across the last L ES observations INCLUDING TODAY; require L observations and count ties. Thus L20 includes today and 19 earlier closes. A breadth confirmation is its own closing value >= its own L-observation maximum including today, with full history. Compute each series' flags before joining dates. Require all four valid breadth flags to classify zero confirmations versus some (1–4). Unknown history must not be treated as nonconfirmation.

Primary: ES high at L20 AND average closing breadth>=80. Level partitions: below50; [50,80); >=80. For each L report all highs, three level groups, no confirmation, some confirmation and all confirmation-eligible highs: 21 overlapping conditions. Four horizons and four counting policies give 336 result rows. No additional level thresholds are searched in this rerun. Config was recorded before this recalculation, but choices and dates had already been explored, so this is not a new preregistration.

Optional recent confirmation means an own-series high flag TODAY or on the preceding FOUR source observations. Require all five flags valid (L+4 observations), and require this history in all four series for a shared denominator. At L252 there are 370 ES highs, 306 same-day-eligible highs (64 excluded), and 303 recent-five-eligible highs (67 excluded). Same-day zero confirmations occur on 270/306=88.2%, median count zero. Fresh recent-confirmation counts on 303 dates: 3 (5-day),4 (20-day),15 (50-day),48 (200-day), or 1.0%,1.3%,5.0%,15.8%. Old narrative reported 1.3%,1.3%,5.6%,17.0%; its precise old code/eligibility/recent-window rules are unavailable. Do not claim exact reproduction of those percentages.

Made-up examples: ES close5100 ties the prior19 maximum5100 and qualifies at L20. Breadth [100,90,80,50] averages80 despite one reading50. A breadth close70 fails own-window confirmation if the maximum was90; a close45 confirms if it is that window's maximum. Confirmation and breadth level therefore differ.

An additional definition audit uses today's ES close STRICTLY ABOVE every one of the preceding20 closes (today excluded). On the primary mean>=80 condition it selects the identical55 dates with identical outcomes. That identity is not asserted for other signals/lookbacks. Both audited definitions are reported rather than choosing by outcome.

## Entry timing and outcome calculation

After both daily observations complete, for signal full-ES row i enter the opening reference at i+1; exit at close i+h for h=1,3,5,10. Chart-price change (%) =100*(exit/entry-1). One session opens/closes the next ES row; ten sessions exit the tenth later row. Use full ES calendar BEFORE joining breadth, not a filtered date sequence. A source session is an observed row, not a calendar day. Dates alone do not establish actual publication latency: completed breadth must be available before the chosen next-open reference, which is an unverified execution assumption.

Missing forward outcomes are excluded per horizon, not zero. All-date denominators: 2450,2448,2446,2441. All L20 ES highs have572 next-session versus571 ten-session windows. Below50 group has19 next-session versus18 ten-session windows. Primary55 signals all have complete outcomes, January22,2018–August30,2024; none later in the frozen sample.

Means weight windows equally; positive means strictly gross change>0, with flat windows retained in denominator. Median is the middle sorted change, averaging the two middle ones for even n. Min/max are individual windows, not account drawdown. These are not compounded returns.

## Counting policies and references

Every qualifying date may produce overlapping multi-session windows. First consecutive signal date requires today's full condition true and previous common-date observation false; 55 primary dates give37 runs. Consecutive means common available observations, not calendar days. Run starts are set on all dates then incomplete outcomes excluded. Nonoverlapping selection greedily accepts first measurable signal then another only at full ES row >= last accepted row+h. Five-spacing uses gap5 for every horizon, so ten-session windows still overlap. Single-session windows already do not overlap at one signal per date, but may remain dependent on adjacent market conditions. Different runs/windows are not proven independent economic episodes.

Ordinary market baseline uses all common dates with complete outcomes. High-state baseline uses all ES-high dates for that lookback, or all confirmation-eligible highs when comparing confirmation groups. For a calendar reference, match every event with all OTHER complete common-date outcomes in the same signal year and weekday. Other signals may remain; average their changes per event and average those event references. Mean excess=average(event minus reference), in percentage points from unrounded values. It is an observed-sample descriptive benchmark, not a live feature, volatility control or causal comparison.

One-point long-reference scenario (%)=100*(exit-entry-1)/entry, one assumed point for the full round trip, not each side. This is not measured commission/slippage or a calculation of short-trade profitability. Earlier/later groups split at2022-01-01; both were previously examined, so no untouched validation is claimed.

## Findings and limitations

Primary55-event means: next session -0.142381%,22 positive;3 sessions -0.400135%;5 -0.638152%;10 -0.921059%. First-of-run next mean -0.177495% across37,16 positive. Five-spacing next mean -0.249534% across30,10 positive. Five-session nonoverlap mean weakens to -0.165014% across30,17 positive. Ten-session nonoverlap remains -0.946977% across22. Do not claim only the next session matters. Later period primary next mean is more negative, but has only18 signals. Generic zero-of-four L252 confirmation has positive next mean +0.051935% across270; missing confirmation alone was not automatically bearish here.

The ES series is continuous chart data without dated-contract, roll or historical-adjustment metadata. Both new-high signals and forward changes may be affected. We cannot remove cross-contract changes or certify adjustments. Chart-price associations are not verified executable-contract P&L. Actual stock membership, eligible denominators, provider revisions, publication timestamps and fills are not independently audited. No stops, entry path, position sizing, margin, funding, roll trades, actual shorts or account equity are modeled. These previously explored choices and periods, related breadth studies and overlapping events are not independent confirmations. No confidence interval, search-adjusted significance or forecast probability is claimed.

## Package and verification

`analysis-config.json` records definitions/cutoffs; `reproduce.py` constructs high/level/confirmation flags, variants, counts and periods; `breadth_base.py` validates inputs and supplies full-ES-calendar outcomes, spacing, costs and matched references. `verify.py` separately reads CSV records, constructs list-based rolling maxima and recent flags, recounts all variants and uses csv/statistics forward arithmetic. Nine made-up checks cover ties/history, an old high leaving a window, mean80 without all-series80, unknown confirmation, a missing breadth date within the ES calendar, five valid recent flags, run resets, spacing boundaries, missing/flat outcomes and illustrative cost arithmetic. Actual record: 36,248 independent value comparisons and all336 aggregate rows passed; source fingerprints match.

`results/summary.json` includes input checks, source hashes, ordinary/high-state results, confirmation denominators, period comparisons and alternate-definition audit. `results/highs_summary.csv` contains336 aggregate rows with condition/horizon/policy, events, mean/median, positive count/rate, one-point scenario, calendar reference/difference, extremes and measured first/last dates. `results/verification.json` records actual checks and source-claim comparison. Daily bars, breadth records and event prices are excluded.
