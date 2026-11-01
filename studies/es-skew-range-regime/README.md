# Did low SKEW readings precede larger ES price ranges?

Checked October 16, 2026. Historical chart-data research; no trade or profit claim.

## Question and finding

Did a low completed SKEW close relative to its previous two years precede larger ES ranges? Yes in this saved history: the next-week mean range is 4.4956784491% for 257 low weeks versus 2.7888432282% for 377 high weeks. Eligible signal dates span October 6, 1997–September 14, 2026; outcomes end September 25, 2026. Low dates: September 20, 1999–August 10, 2026. High dates: October 6, 1997–February 24, 2025.

Much is already visible in volatility. Low weeks' trailing daily standard deviation averages 1.305929484%, high weeks 0.857141873%. Matched low windows: 255, range 4.5024127751%, reference 4.1418245243%, difference +0.3605882507 percentage points. Matched high windows: 376, range 2.7933810219%, reference 3.0064872779%, difference -0.2131062559 points. This coarse retrospective comparison does not prove incremental prediction. Only 130/257 low one-week outcomes are positive (50.5837%).

## Exact calculation

Map labels into Monday–Sunday calendar weeks. At the end of a completed SKEW week:

```
rank = 100 * count(previous 104 SKEW weekly closes <= current close) / 104
low = rank <= 20; high = rank >= 80; middle otherwise
```

Current close is excluded from history. Equal closes count as <=. Require all prior 104 calendar weeks. Do not round before grouping. Missing history stays undefined. A second audit uses last 104 reported observations across missing calendar weeks; never choose based on resulting performance. The group proportions need not equal 20/60/20 because ranks use changing earlier histories. Made-up: 18 earlier closes <= current gives rank 17.31 and qualifies low; 84 gives 80.77 and qualifies high.

Entry reference = first ES daily open in next calendar week. Exit = final ES daily close in h-th following week, h=1 or 4. Require every forward week to have observations and to be completed. Highest/lowest use all daily bars across those h weeks:

```
range_points = maximum high - minimum low
range_pct = 100 * range_points / entry_reference
direction_pct = 100 * (exit / entry_reference - 1)
positive = direction_pct > 0  # zero is not positive
```

Do not add daily or weekly ranges. Made-up opening reference 5000, high 5100, low 4900, final close 5020 gives 200 points / 4% range, +0.4% direction. No fill is assumed. Four weeks means calendar weeks, not exactly 20 sessions. There is no exact clock time in these date-only bars.

## Volatility reference

Compute each daily arithmetic close-to-close percentage change. At the final signal-week close take the sample standard deviation of last 20 observed changes (21 closes needed): sqrt(sum((change-mean)^2)/19). No annualization. Fixed bands: [0,.5), [.5,1), [1,1.5), [1.5,2), [2,3), [3,infinity). Left edge included. For each eligible signal week with a complete horizon, take all other rank/volatility-eligible weeks in the same signal calendar year and band with that complete horizon; own week excluded. Peers may belong to any SKEW group, including its own. Need at least one peer. Reference = their mean future range. Average per-signal reference means with equal weight; compare only matched signal windows. Two low and one high window lack peers in either horizon; retained in raw summaries, excluded from matched summaries. Counts/minimum/median peer sizes are saved. Example: peers 3%,4%,5% average4%; signal4.5% differs by +.5 percentage points.

This is a retrospective explanation: peers can be later in the year and share future price windows. It is not an available-at-entry trading forecast, randomized comparison, causal estimate or significance test. Fixed coarse bands retain within-band differences; minimum one peer can be weak. Main signal ranks/volatility do not use future data.

## Counting and summaries

Each window gets equal weight. Means sum values/count; medians use middle order statistics; positive percent = positive count / measured windows *100. All eligible baseline uses same rank/volatility eligibility, including signal weeks. First-run policy keeps first week of uninterrupted group runs; missing or other-group week breaks a run. Nonoverlapping policy greedily keeps earliest complete window then spaces signals by at least h calendar weeks, separately within each group. Within-group nonoverlap does not remove shared market episodes or across-group overlap. Period checks use signal years 1997–2009, 2010–2019, 2020–2026. Full-year peer references are still same-year. All definitions frozen in analysis-config.json before new calculation; source already explored many ideas, so not independent validation.

## Inputs, dates, gaps and limitations

Provide appropriately licensed copies in --input-dir. CSV columns required: time (YYYY-MM-DD date label), open, high, low, close. Other columns ignored. Require ordered unique dates, finite positive consistent OHLC, unique SKEW week labels. Sources are saved chart exports; original bars and event prices are deliberately excluded from this repository.

| Input | Rows and source dates | SHA-256 |
|---|---|---|
| `CME_MINI_ES1!, 1D_c578e.csv` | 7,351; 1997-09-09–2026-10-02 | `44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4` |
| `CBOE_DLY_SKEW, 1W_a7232.csv` | 1,915; 1990-01-01–2026-09-28 weekly labels | `3758569910b82712d2d7d97732ed2e9a7f718de77dcd637ff933c9d3bb172383` |

Exclude whole developing week starting September 28, 2026 (5 ES rows, 1 SKEW row); last completed week starts September 21 and ends September 25. Remap 133 holiday Tuesday/Wednesday labels without inventing values. Missing SKEW weeks: 2000-09-25, 2014-03-17, 2014-04-07. 1,513 common weeks; 1,303 with complete prior 104-calendar-week history; 4 initial ES weeks lack 20 daily returns, leaving 1,299 eligible (257 low / 665 middle / 377 high). Missing next outcome removes 1 middle week at 1 week and 4 middle weeks at 4 weeks, giving baselines of 1,298 and 1,295 windows. No missing prices filled. Holiday-shortened weeks allowed; no entirely absent ES calendar week in frozen overlap. Individual missing days need a provider calendar audit. First ES week partial.

Continuous ES has undocumented contract/roll/adjustment handling. Both range and direction may include roll artifacts. Point ranges reflect changing nominal prices and are not present-day stop distances. SKEW early history is reconstructed: [Cboe's introductory paper](https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf) discusses 1990-era history when introducing the index. Date labels do not establish live release timing or executable next-open prices. Fees/slippage not deducted from ranges because no trade simulated. No risk sizing, intraday strategy or direction/momentum combo tested.

## Earlier evidence and overlap

Source: earlier Backtesting ES weekly SKEW discussion and recovered chart exports. Older claim next-week 4.58% / 2.70%, four-week 8.72% / 5.69% (low/high) does not reproduce as a set under either documented history rule. One reported-history mean rounds to 4.58%; exact earlier handling/code unrecovered. No search to make remaining figures match. Older regression, bootstrap, significance/barrier and intraday implications are unverified. This focused check has 2 history definitions × 4 groups × 2 horizons × 3 counting rules = 48 aggregate rows, plus period summaries; no newly tuned rank/band cutoffs. Ideas previously explored, no independent validation or future-probability claim. Related es-skew-weekly-collapse uses same inputs; distinct within-week-change question, not independent confirmation.

## Reproduce

Python 3.12.14 used. Install pinned requirements in a suitable environment:

```
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /path/to/licensed-chart-exports
python -B verify.py --input-dir /path/to/licensed-chart-exports
```

Outputs: results/summary.json, results/range_summary.csv (48 aggregate rows), results/verification.json. Running replaces these summaries, never original inputs. Independent verifier uses csv/date/statistics arithmetic to recount ranks, daily volatility, forward ranges/direction, peer matching, counting and periods: 14,841 comparisons and 9 made-up fixtures passed. Numeric comparison tolerance 2e-10; same source hashes confirmed. This package contains code/docs/configuration/aggregate statistics only. Article review and publication handled separately by owner; no fabricated approval.
