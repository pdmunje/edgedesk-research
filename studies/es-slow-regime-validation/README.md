# Did slow moving-average filters improve later ES direction?

Corrected recheck, October 17, 2026. The four earlier diagnostic definitions remain fixed; all four later-period day-weighted comparisons are negative. This does not test signal persistence or imply that every possible trend filter fails. Later-period results were already examined in earlier work, so they are not fresh untouched evidence.

## Input and reproduction

Use a separately licensed reconciled one-minute ES Parquet file with SHA-256 `2a794cbeae8f8fc3022d4079e98c32e8d9dc030ba1d1bda2b457aa857f0fa6f9`. It is not redistributed. Required fields: timestamp_utc (timezone-aware UTC), open/high/low/close/volume, underlying_contract, price_source, volume_source, quality_state, roll_session, roll_transition (Boolean), is_complete (Boolean). Prices finite/positive and OHLC consistent; timestamps sorted and unique. Extra fields ignored. No account identifiers, proprietary bars, event-level prices, original chats, machine paths or website/application code are included.

Python 3.12.14 was used. Install pinned dependencies in a suitable environment and run:

```
python -m pip install -r requirements.txt
python -B reproduce.py --input /path/to/licensed/1m_v1.parquet
python -B verify.py --input /path/to/licensed/1m_v1.parquet
```

Aggregate outputs are written under results/ (optional --output for the calculator). The verifier reads bundled results/. article-summary.json is an editorial extraction of those aggregate results, not an additional data source. The calculator overwrites its generated summaries and never changes the licensed input. CSV precision is 10 significant digits; full precision is used while calculating. Full-grid runtime and memory are substantial because it evaluates millions of observations; no external data or paid computation service is called.

## Dates, session clock, quality and rolls

Source: 4,931,583 complete rows, June 6, 2010 22:00 UTC–September 11, 2026 00:19 UTC, zero duplicate timestamps, 65 roll transitions. Convert timestamps to America/New_York with daylight-saving changes. Session is 18:00–17:00 next day; remove 17:00–18:00 rows before ALL feature/outcome calculations (347 removed, 4,931,236 remain). Trading date is local calendar date plus one if local hour>=18. Do not fabricate missing bars. Original contract segment=cumulative sum of roll_transition before maintenance removal, so a removed roll flag still separates contracts.

Use supplied unadjusted prices and provided roll flags. The source declares contract choice using prior-session volume; this rerun does not independently rebuild that selection. Vendor-degraded complete rows retained: original quality/source counts saved in data_audit.json. Gaps include closures and missing coverage. Final session and 2026 partial. Horizons count observed eligible source rows, not elapsed minutes.

Development labels 2015–2022; validation 2023–2024; already examined later period 2025–latest; historical check 2010–2014. Labels follow decision trading date. Exclude outcomes crossing predefined period boundaries or roll segments. Features may legitimately use earlier observations within the same contract, including before a period starts. Annual/grouped references use their own decision-date group; outcomes can cross years within one predefined research period.

## Four unchanged diagnostics

- Long; 60 observed bars: SMA(2760), price above it, average above its value 15 observed bars earlier.
- Long; 240 observed bars: SMA(2070), price above it, average above its value 30 observed bars earlier.
- Short; 60 observed bars: WMA(480), price below it, average below its value 15 observed bars earlier.
- Short; 240 observed bars: SMA(930), price below it, average below its value 240 observed bars earlier.

All conditions use decision close. Above/below, rising/falling strict: equality does not qualify. Missing average/slope excluded. Definitions were chosen in older research, not retuned on this recheck. frozen-definitions.json contains them without new outcome selection. frozen_candidates.json adds their remeasured development/validation comparisons.

## Exact average formulas and search grid

SMA(N)=sum(last N eligible closes)/N. WMA(N)=sum(j*close_j for oldest-to-newest weights j = 1..N)/(N*(N+1)/2). EMA alpha=2/(N+1), ema_now=alpha*close_now+(1-alpha)*ema_previous, seeded with first close of a contract segment; report after N observations. All restart at roll. Slope sign compares average[t]-average[t-K], requiring same segment and both values available. Scaled slope=(average[t]-average[t-K])/close[t]/K; distance=(close-average)/close.

Example: closes 100, 101, 103 yield SMA(3)=101.3333, WMA(3)=(100+202+309)/6=101.8333, EMA(3) (alpha .5, first seed 100)101.75. Current close 103 above all, but slope condition still needs earlier specified average. These are made-up values.

Grid: SMA/EMA/WMA lengths 480,690,930,1100,1200,1380,1500,1650,2070,2760,4140,6900. Slope intervals 15,30,60,120,240. Price above/below states and aligned price+slope states. Discovery-only quantiles at .2, .4, .6, .8 split distance/scaled slope into five groups, linearly interpolated; exact boundary enters upper group, missing stays missing. Reuse edges for validation. Extreme distance groups are in candidate table; all five validation means in bucket file. All failed/empty states retained; empty means undefined, never zero.

Line-fit lengths 480,690,930,1380,2070,2760,4140,6900. Fit y=close versus x=0..N-1. slope=sum((x-meanx)*(y-meany))/sum((x-meanx)^2); fitted last=meany+slope*(N-1)/2. Residual size=sqrt(sum((y-fitted_y)^2)/N); quality=slope*(N-1)/residual_size. Zero residual makes quality undefined. R-squared is fitted explained variation/total centred variation, with zero total variation set to 0. Only quality buckets create the reported regression conditions. This is not a claim every regression or R-squared alternative was tested.

EMA stacks [480,1380,2760] and [1380,2760,6900]. Bull score 0..8 = 3 price-above votes + 2 shorter-above-longer votes + 3 positive 60-bar-slope votes. Bear reverses comparisons; equality gives no vote. Signed=bull-bear. Strong bull/bear>=7 (not necessarily 8), neutral abs(signed)<=1. Require ALL averages/slopes available before any stack score classification. Score levels retained, not only strong groups.

Bucket/score ordering flag uses Pearson correlation of bucket index with validation mean, sign reversed for intended negative-feature short ordering. Clear: correlation >= .9 and >= 75% adjacent changes favourable; approximate >= .6; weak >= .25; otherwise nonmonotonic; fewer than 3 finite means insufficient. It is descriptive, not Spearman significance or a validation probability.

## Outcome and reference formulas

For H = 60 or 240, long_fraction=(close[t+H]-close[t])/close[t]; short_fraction=-long_fraction. Output percent=100*fraction; basis points=10000*fraction; 1 basis point = .01%. Positive strictly>0; flat counts in denominator but is neither long-positive nor short-positive. Decision close is a price reference, not an established executable fill.

Per evaluation period and side/horizon, compute average eligible return for each New York session-minute slot. This includes signal observations themselves. For every qualifying decision, excess=its return-its slot mean. Equal-minute extra mean=average excess. Equal-day extra mean=first average excess per trading date with at least 1 signal, then average those date means equally. Same-clock baseline may use later dates and is retrospective; no year/volatility matching or available-at-entry forecast claimed.

Made-up weighting: 100 minutes on day A each +1 bp, 1 minute on day B -10 bp. Equal-minute=(100-10)/101=+.891bp; equal-day=(1-10)/2=-4.5bp. Observations overlap heavily; these are not 101 independent market episodes. A 60-observed-bar horizon can last more than 60 clock minutes. A hypothetical 6000 to 6006 long change=.1%=10bp; short mirror=-10bp. One basis point at illustrative 6000 = .60 ES point, not a historical constant-price profit calculation.

## Uncertainty and other outputs

Day bootstrap: use each selected date's mean excess; sample these dates with replacement 500 times with seeded RNG 20261002; each resample average, take 2.5% / 97.5% quantiles. Not a future-return prediction interval. Does not remove serial dependence across days, correct all searched parameters or refit historical references each resample. Original future period already opened; no independent validation claim.

Favourable/adverse excursions use future highs/lows t+1..t+H, each magnitude clamped>=0. Long favourable=max(0,maxhigh-close), adverse=max(0,close-minlow); short reverses. Tick = .25 point. Secondary stack barrier target 8 points / 32 ticks, stop 6.25 points / 25 ticks; scan bars in order. Same-bar initial touches of both barriers unresolved because intrabar order unknown; output unresolved_or_no_touch_pct combines these with neither-touched windows. Category totals checked, but full per-source-path secondary flags are not independently recounted. They are not trade wins/fills. Full fixed-rule distributions, same-clock probabilities, yearly/grouped summaries and grid retained.

## Corrections and evidence

Old rolling regression used 1..N weighted sums with 0..N-1 centering; subtracting one extra window sum fixes the origin. Made-up independent slope 1.93 versus old 56.94 exposed it. Old maintenance rows were excluded as anchors but entered features/horizons. Old future windows could cross evaluation splits, missing stack history counted neutral, and excursion magnitudes could be negative. This recheck corrects these issues and labels bucket correlation/unknown barriers honestly. Old numerical results need not match, and old selection cannot retroactively become untouched evidence. No new rule selection follows these repairs.

Full corrected grid: 2,928 candidate rows, 908 bucket rows. Ten direct mathematical checks and 672 independent metric comparisons across 32 fixed-rule period/side distributions passed. Independent MA calculation uses pandas rolling SMA and a weighted-sum recurrence for WMA; outcomes/references/extrema/day balancing/bootstrap recounted separately. Source fingerprint unchanged. Verification tolerance 2e-8 relative / 1e-7 absolute includes aggregate CSV rounding. Other grid cells run through these checked kernels; not every full-grid cell receives a separate independent recount.

This remains a before-cost chart-distribution study. No actual entry fills, fees/spread/slippage, trading frequency, position sizing or executed system profit. Related momentum persistence, short-window discovery and overlapping-minute work share inputs or questions; not independent confirmation. Human review of this exact article/package required before publication.

## Result-column guide

- candidate / family / ma_type / length / slope_horizon / state identify the exact rule or searched state. period / year / subperiod identify the decision-date group. direction is LONG or SHORT; horizon counts later observed eligible bars.
- raw_observations counts qualifying decision anchors with complete eligible future outcomes. Adjacent anchors can use overlapping future prices. distinct_trading_days and distinct_years count represented decision dates and years. coverage_pct in the candidate grid counts state-qualified decision bars divided by all source bars in that period, before future-outcome exclusions; it is not raw_observations divided by a trade count.
- positive_pct is the percentage of complete outcomes strictly above zero. matched_baseline_positive_pct averages same-clock positive fractions across those decisions; excess_positive_pp is their difference in percentage points.
- mean_return_pct / matched_baseline_mean_return_pct are intended-side chart changes in percent. excess_mean_return_bp or matched_excess_mean_bp subtract the same-clock reference and express the difference in basis points. One basis point = 0.01% of starting price. day_balanced_mean_excess_bp first averages extra changes within each signal trading date and then weights those dates equally.
- median_return_pct is the middle measured outcome. p10 / p25 / p75 / p90 return fields are the respective outcome percentiles, using linear interpolation. They describe sampled outcomes, not confidence limits or future forecasts.
- MFE means maximum favourable excursion; MAE means maximum adverse excursion. Values in these columns are ES points from the decision close, clamped at zero. mean and median are across eligible anchors; MFE_MAE_ratio divides their two means, not the mean of each individual ratio.
- day_block_ci_low_bp / high_bp are the 2.5% and 97.5% quantiles of the 500 resampled day-average results. The seed and resampling limitations are stated above; these are not IID-minute confidence limits.
- target_first_pct / stop_first_pct / unresolved_or_no_touch_pct partition the eligible anchor sample, including ambiguous same-bar touches in the final category. These are chart-path labels before execution and costs.
- Q1 through Q5_excess_bp fields retain every validation bucket mean comparison, with missing groups left undefined. bucket_index_correlation is ordinary centred correlation of group order and measured means, with the documented directional sign choice; it is not a Spearman test or a significance level. classification applies the descriptive thresholds stated above.

For correlation: subtract the mean from each group position to get a, subtract the mean from each measured group mean to get b, then calculate sum(a*b) / sqrt(sum(a*a)*sum(b*b)). The full grid is retained so the searched region and failures can be inspected, not to treat each row as independent evidence.
