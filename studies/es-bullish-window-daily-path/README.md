# What made these historically bullish ES windows positive?

Checked October 16, 2026. Recheck of an already explored Backtesting ES 2 research lead. Charts and historical reference comparisons; no executed-trade profit or causal forecasting claim. COT is explicitly excluded because actual historical release timing is unverified.

## Finding and dates

For 200-day breadth, 35 nonoverlapping ten-session windows have 188 positive close-to-close days / 350 distinct sessions = 53.7143%, against weighted same-year/entry-weekday references of 49.6912% (full exact values in summary). Mean positive day +1.35% versus +1.01%; mean negative day -1.11% versus -1.00%. Entry dates 2018-10-15–2025-04-29, final outcome 2025-05-12. 50-day breadth uses 32 windows, 320 days, entries 2018-02-12–2026-03-20, outcome 2026-04-02. Simple SKEW uses 100 windows, 2,000 days, entries 1998-02-09–2026-08-03, outcome 2026-08-28. Do not compare these differing histories/horizons as competing strategies or add their samples as independent evidence.

## Inputs and completion

Bring appropriately licensed chart exports into --input-dir. Every file requires ordered, unique YYYY-MM-DD time labels and open/high/low/close; values finite, range-consistent. ES/SKEW positive; breadth values 0–100. Other columns ignored. No provider bars or event prices redistributed.

| File | Rows; source date labels | SHA-256 |
|---|---|---|
| `CME_MINI_ES1!, 1D_c578e.csv` | 7,351; 1997-09-09–2026-10-02 | `44f95b0d4e80305a7c5e19b87aa8f29b222a0c60b3ece8b25871aea1ba58daf4` |
| `INDEX_S5TH, D_0f94a.csv` | 5,094; 1990-10-15–2026-10-01 | `2f89dbf2b120291b69cf3b116df371fe1eec1ea5e73f47b6c799e1af34a50289` |
| `INDEX_S5FI, D_96a6d.csv` | 4,992; 2006-12-29–2026-10-01 | `25910ae25f8c7525351f88394580414ceab3c00c488267d414609cbd48af8c84` |
| `INDEX_S5TW, D_dc629.csv` | 4,992; 2006-12-29–2026-10-01 | `84d372d91bee78ba3aa6944e95f4e5a9eea91c80ef8e8587bf83b98af6bb4825` |
| `INDEX_S5FD, D_905a5.csv` | 2,451; 2017-01-03–2026-10-01 | `05377c278f8c6cc8d734a37ca1405ae77f9ced9d4d28ca821d54c3427f7b0c1f` |
| `CBOE_DLY_SKEW, 1W_a7232.csv` | 1,915; 1990-01-01–2026-09-28 | `3758569910b82712d2d7d97732ed2e9a7f718de77dcd637ff933c9d3bb172383` |

ES frozen at 2026-10-01: saved 2026-10-02 bar was developing at export. There are 7,350 completed daily observations. SKEW frozen at week starting 2026-09-21: saved 2026-09-28 weekly bar excluded as developing. Map 133 holiday Tuesday/Wednesday labels into Monday-Sunday weeks, preserving reported values. Missing SKEW weeks 2000-09-25, 2014-03-17, 2014-04-07. No filling. Breadth eligibility is common ES+all four breadth dates (2,451, 2017-01-03–2026-10-01) to retain earlier study's universe, even though only 200/50 series trigger these rules. Each selected series has 5 zero-range days; undefined recovery never qualifies. Keep full ES observation sequence before intersecting signal dates. Horizons are observed rows, not fixed calendar days; missing provider sessions need calendar audit. Require full horizon before counting any path point; late signals without it excluded.

## Conditions and timing

```
recovery = (breadth close - breadth low) / (breadth high - breadth low)
breadth200_partial: 200-day breadth low <=40 and .40 <= recovery < .75
breadth50_partial: 50-day breadth low <=30 and .40 <= recovery < .75
```

Both use next ES observed daily open, then 10 observed sessions including entry session. Breadth day must complete first; high=low makes recovery undefined. Made-up breadth low 30, high 50 and close 42 gives .60 and qualifies; close 45 gives .75 and does not. 200/50 refer to moving averages of constituent stocks, not outcome lengths. Provider breadth accepted rather than reconstruct historical constituents.

```
change = completed weekly SKEW close - weekly open
skew_drop5: change <= -5 index points
scaled change = (current change - mean(previous 104 changes)) / sample_sd(previous 104 changes)
sample_sd = sqrt(sum((prior change - prior mean)^2)/103)
normalized rule: scaled change <= -1.5
```

Current week excluded. Main normalized history requires all previous 104 calendar weeks. Reported-history audit uses previous 104 actual reported changes across gaps. Zero SD undefined. Simple made-up SKEW open 150 / close 145 qualifies -5; close 145.01 does not. All SKEW versions use first ES open in next calendar week then 20 observed sessions. These are within-week changes, not low closing SKEW rank. See [Cboe's introductory paper](https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf) for index and reconstructed early history. Date-only labels do not establish time zone, live release timing or executable opening fills.

## Window selection and references

Primary: sort complete qualifying entries, keep earliest, then next entry>=last kept+h source sessions, separately per condition. No held day repeats within a main rule. Different rules can overlap; adjacent windows can share boundary prices and market regimes. Audit also counts every complete signal, deliberately repeating held days. Do not call those appearances independent.

For each event, choose full ES windows starting same calendar year and weekday as its entry. Exclude any window sharing a held session with event. Greedily retain earliest remaining references with h-session spacing; need 1 or more. References may satisfy any signal. Each event gets equal total weight, references within it equal weight. Each reference day's weight=1/number_of_reference_windows_for_this_event. With equal h, total day weight per event=h. References can recur across comparisons, so reference appearances are not independent samples. Count all appearances and distinct reference sessions in summary. Same-year matching can use later dates; retrospective explanatory comparison, not available-at-entry forecast. Volatility and other conditions not matched.

## Measurements, signs and denominators

```
close_to_close_pct =100*(today close/prior observed close -1)
open_to_close_pct =100*(today close/today open -1)
prior_close_to_open_pct =100*(today open/prior observed close -1)
daily_range_pct =100*(today high-today low)/today open
window_change_pct =100*(last held close/entry open -1)
```

Positive strictly>0; negative<0; flat=0. Signal positive percent=positive held-day appearances/all held-day appearances*100. Positive mean sums changes ONLY on positive sessions / positive-session count. Negative mean analogously, retaining minus sign. Flat days included in frequency denominators. Range mean across all days. Window positivity uses windows denominator, not days. Weighted reference frequencies use sum(positive-day weights)/sum(all day weights), signed means sum(weight*change on signed days)/sum(weights on signed days). Reference mean window change averages reference windows within each event, then events equally.

Made-up 10 days: 5 gains +1%, 4 losses -.5%, 1 flat  => 50% positive, mean gain +1%, mean loss -.5%, daily mean +.30%. Exact daily identity:mean=p_positive*mean_gain+p_negative*mean_loss. Percentage changes compound, so do not multiply daily mean by h or sum cumulative path. First day close-to-close includes pre-entry gap. Made-up prior close 100 / open 110 / close 111 gives 11% close-to-close, 10% gap and .9091% open-to-close; opening entry cannot earn pre-entry gap. Per-day exact link:(1+cc/100)=(1+gap/100)*(1+oc/100); averages need not obey that product. Daily-path row d uses same full-h cohort, cumulative = 100 * (close[entry_index + d - 1] / open[entry_index] - 1), daily O→C and count C→C>0. All sessions 1 through h are saved, not only article checkpoints.

## Earlier claims and gaps

Breadth all-signal means +2.26% (82 windows) and +2.68% (71 windows) reproduce, as do positive-window counts 64 / 82 and 58 / 71 and rounded up-day frequencies. Earlier positive/negative daily-size claims +1.29% / -1.01% and +1.29% / -.97% do not match the explicitly pooled close-to-close means +1.26% / -1.04% and +1.26% / -1.01% here. The exact old code and aggregation conventions were not recovered. The new reference removes shared and overlapping held sessions, so its baseline need not match the earlier one.

The reported-history SKEW audit has 111 complete signals: mean window change +1.85%, 78 / 111 = 70.3% positive windows, and 54.5% up days. These rounded headline values match the earlier daily-path narrative. Daily sizes +.92% / -.91% differ from the older +.94% / -.87%. This does not resolve the earlier weekly study's different normalization count. The calendar-history version has 89 all-signal and 69 spaced windows; the reported-history audit has 111 all-signal and 83 spaced windows. Never choose between them by which looks best. Simple SKEW has 155 all-signal and 100 spaced windows. Twenty observed sessions differs from four calendar weeks in the related study.

COT source's release timestamps expressly nominal with holiday verification missing; retrieval timestamp does not establish historical availability. No causal COT result calculated/claimed. Needs actual release evidence. Source studied many families/thresholds; this synthesis has no independent confirmation, new untouched sample, confidence interval, significance test or era validation. It shares inputs with breadth recovery, SKEW weekly collapse and SKEW range studies.

## Data/trading limits

Continuous ES has undocumented roll/adjustment and contract-selection conventions, possibly distorting gaps and returns. Early SKEW history reconstructed. No audit of revisions/live availability, no verified fills or actual contracts, no intraday target/stop/direction-momentum test. No fees/spread/slippage deducted: changes are chart measures, not profits. Larger historical ranges alone do not establish long-only permissions or stop sizing.

## Reproduce and checks

Python 3.12.14 with pinned dependencies:

```
python -m pip install -r requirements.txt
python -B reproduce.py --input-dir /path/to/licensed-exports
python -B verify.py --input-dir /path/to/licensed-exports
```

Outputs overwrite this package's results/summary.json, distribution_summary.csv (30 aggregate rows), path_summary.csv (160 aggregate rows) and verification.json. Original inputs remain unchanged. Independent csv/date/statistics recount checks exact signal entries, all 2,230 reported numeric/date values, nonrepeating primary held days, weighted comparisons, paths and daily decomposition identity. Ten invented boundary checks pass; SHA-256 fingerprints verified. Numeric tolerance 2e-10 relative / 2e-9 absolute. Only code/docs/config/aggregate summaries in this package. No original bars, event prices, machine paths, credentials, private application code or chats. Human review of exact version required separately before publication.
