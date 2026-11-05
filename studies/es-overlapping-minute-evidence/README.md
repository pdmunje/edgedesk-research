# Overlapping windows and different day weights

Question: why can the average qualifying minute and the average signal day give opposite signs, and how should uncertainty be calculated? Two already examined examples illustrate separate issues: overlap reuses movements; weighting changes which average is estimated. No new edge, no effective-independent-sample-size estimate and no executed trading profit.

## Reproduce

Python 3.12.14; install pinned requirements, then:

    python -m pip install -r requirements.txt
    python -B reproduce.py --input /your/licensed/1m_v1.parquet
    python -B verify.py --input /your/licensed/1m_v1.parquet

Input is licensed, not distributed. SHA-256 must be 2a794cbeae8f8fc3022d4079e98c32e8d9dc030ba1d1bda2b457aa857f0fa6f9. Schema: timestamp_utc timezone-aware UTC; positive finite close; Boolean roll_transition and is_complete; quality_state and price_source text. Original date range 2010-06-06 22:00:00+00:00 through 2026-09-11 00:19:00+00:00; 4931583 complete rows. Default results/ aggregates only; --output may select another output folder, but verifier reads default results/. No per-minute observations or vendor prices are emitted. Source construction is an existing unadjusted, prior-session-volume contract selection; not independently rebuilt. Do not silently substitute another input and retain these claims.

## Fixed teaching examples and dates

slow_short_60: close below weighted mean of last 480 eligible closes AND that average below its value 15 bars earlier; measure negative of the later long change over 60 observed bars. WMA = sum(j*close[t-N+j], j=1..N)/(N*(N+1)/2), newest gets weight N. rebound_long_240: close below SMA120 AND that average lower than 60 bars earlier; measure long change over 240 bars. SMA=mean(last N closes). Strict inequalities, missing values excluded; features reset at each contract change. These cases were selected after seeing prior results for an explanatory article. Their rule definitions remain unchanged; no new search or untouched validation.

Remove New York 17:00–18:00 maintenance rows before all features/outcomes, but derive contract segment IDs before removal so a maintenance roll flag is preserved. Trading date: 18:00 previous calendar day through before 17:00, DST aware. Four periods based on decision trading date: 2010–2014,2015–2022,2023–2024,2025–latest. Exclude future windows crossing broad periods or contract segment; gaps/weekends/sessions can be crossed. Horizons are observed bars, not elapsed minutes. Final session/year partial. Complete vendor-degraded rows retained without price repair. No duplicate timestamps; cleaned gaps audited.

## Exact averages

Long outcome in basis points=10,000*(close[t+H]-close[t])/close[t]; short outcome is its negative. 1 basis point=.01% of price; invented 6000 implies .60 point per basis point. Decision close is measurement reference available only after completion, not a promised fill. For each period/side/horizon, slot reference=mean outcome of all eligible decisions at that New York session-minute label, including signal decisions and later dates. Retrospective, not live forecast; no separate volatility/year matching. Extra change=outcome-reference.

For date j, count n[j] and average extra a[j]. Minute average=sum(n*a)/sum(n), day average=mean(a) among signal dates only. Covariance=mean((n-mean(n))*(a-mean(a))) with population denominator D, the number of signal dates. Minute minus day average=covariance/mean(n). This is arithmetic, not a causal result. Invented days: 3 signals at +1 on A, 1 signal at -2 on B gives +.25 per minute versus -.50 per day. Equal day weighting does not itself fix dependence and is not a once-per-day trade result.

Resample whole signal-date groups with replacement 1000 times; each selected date brings its count and extra mean. Minute bootstrap uses sum(sampled n*a)/sum(sampled n); day bootstrap uses mean(sampled a). Report separate 2.5/97.5 percentiles for each. NumPy default_rng; seed first 8 bytes SHA256 of 20261019|case|period, little-endian. Fixed historical slot references are not refit. Cross-day dependence and windows crossing days persist; no adjustment for original parameter searches or chosen examples. Not prediction intervals. Earlier studies used different seeds/counts; exact CI endpoints need not match.

## Overlap and column guide

observations=eligible qualifying minutes; signal_days=distinct decision trading dates with >=1 signal. Counts per signal date (mean/median/min/max) describe unequal weights. top_tenth_days_count=ceil(D/10), at least 1; its signal share=100*sum(largest counts)/all signals. weight gap=minute mean-day mean, in bp; count_effect_covariance has count*bp units, division by mean count returns bp. All *_extra_bp/interval endpoints/weighting_gap_bp are basis points of price change. horizon is observed-bar count. Period labels are in config; later is already examined. Counts and both centers agree with prior corrected studies; new intervals are separate recalculations.

successive_signal_pairs=N-1 ordered qualifying-anchor pairs. A pair overlaps future steps when same contract segment and index gap<H. overlapping_successive_pairs_pct=100*overlapping pairs/(N-1), including nonoverlapping pairs in denominator. Greedy nonoverlap: take earliest qualifying index, next at least H indices later, reset at roll. Adjacent selected windows may share endpoint, but no future price increments. Their count is geometric, NOT the number of independent tests. Neighbouring 60-bar windows share 59 steps; 240-bar windows 239. This overlaps return components; percentage denominators can differ. Neither count/horizon nor number of dates is asserted to be an independent sample size.

## Checks and limits

All 8 aggregate rows independently recounted for 176 metrics, plus 9 made-up mathematical checks. Independent SMA uses pandas rolling mean, WMA uses weighted-sum recurrence; references/day grouping via pandas; disjoint windows via per-segment next-allowed endpoint dictionary. Both bootstrap estimators and covariance identity checked. Source hash unchanged. Prior-study agreement contains 32 counts/centers across 8 rows; input/rules overlap means this is not independent market confirmation. No executions, fees, spread/slippage, sizing or tradable nonoverlap schedule tested. Aggregate summaries only. Human review required before publishing the specific version.
