# Opening-range sweep versus plain breakout — checked research

Question: does requiring an earlier opposite-boundary touch improve the later closing breakout? Later 2023–Sep2026 sample: 39/72 paired setting differences positive; settings overlap, later dates already examined, no universal/live edge claimed. All original rules and failures retained. Strict model changes execution, stop rounding, quality and ATR history together; not an isolated entry-price experiment.

## Reproduce

Python 3.12.14, pinned requirements:

    python -m pip install -r requirements.txt
    python -B reproduce.py --input /your/licensed/1m_v1.parquet
    python -B verify.py --input /your/licensed/1m_v1.parquet

Input licensed and not distributed. SHA256=2a794cbeae8f8fc3022d4079e98c32e8d9dc030ba1d1bda2b457aa857f0fa6f9. Schema: timezone-aware UTC timestamp_utc, positive finite open/high/low/close with consistent OHLC, underlying_contract text, roll_transition/is_complete Boolean, quality_state/price_source text. Existing unadjusted prior-session-volume contract choice is not rebuilt. Date range 2010-06-06 22:00:00+00:00 to 2026-09-11 00:19:00+00:00; final session/year partial. Source read-only. Default results/ contains aggregates and one-way fingerprints only, no raw bars/per-trade prices; --output may override, verifier reads default results/. No network or private application dependencies. legacy.py contains original research helper formulas with machine paths removed.

## Grid and clock definitions

Family 1H=23 hourly windows anchored 18:00–17:00 NY, OR1/2/5min;4H=18/22/02/06/10 starts with240min windows, OR1/2/5/15/30;930M=18:00–09:30 withsame five OR lengths;1D=18:00–17:00 withsame five. All clock labels America/New_York, DST aware. Four-hour final14:00–17:00 partial contributes only to legacy ATR, not trades; strict ATR excludes it.18 family/OR choices*2 ATR lengths9/14*2 sides=72 settings. Three models (legacy sweep, strict sweep, strict plain)=216 combinations,4 periods=864summary rows;17 decision years yield3672annual rows. Strict paired comparisons72*4=288rows. No time-of-day optimisation or new winner selection.

Opening range=high/low of first N completed 1min bars. Long requires post-OR low<=ORlow on an earlier minute, then strictly later close>ORhigh. Short is symmetric. Equality counts touch, not breakout. OR's own boundary touches do not count post-OR. Plain uses first closing breakout without touch condition. One first trigger/direction/setting/window; no rearming after last-minute or invalid-risk cancellation. Patterns can trigger at different times, not a causal experiment. All alternatives and opposite-side trades may overlap; no combined portfolio or capital/one-position constraints.

## ATR, stop, execution, data quality

TR=max(high-low,abs(high-prevclose),abs(low-prevclose)), first after reset uses high-low. ATR[n] seed=mean(first n TRs); thereafter(previousATR*(n-1)+TR)/n. Current window uses prior completed parent value. Long stop=min(parentopen,ORhigh-priorATR); short=max(parentopen,ORlow+priorATR). Legacy uses source formulas:90% coverage, exactfirst minute, last minute>=end-2, all OR minutes present,single underlying contract; confirming-close entry, stop activates next minute, fractional tick stop; final available close exit. Incomplete/mixed parents can enter legacy ATR; partial4H affects it too. These are source assumptions, not realistic fills.

Strict requires all expected minutes, exact first/last, single original roll segment and underlying contract. Derive source segments before removing 17:00–18:00 maintenance rows. PriorATR history resets after observed bad parent/segment change; require 9 or 14 earlier complete windows. Entirely absent parents are not synthesized; observed sequence can skip closures/data gaps, not a reconstructed holiday calendar. After filtering partial4H, next TR uses previous complete4H close and can reflect intervening gap. All quality filters are retrospective; future complete coverage is not knowable at entry. No live data-dropout fallback.

Strict long stop rounds down to .25 tick, short up. Enter next minuteopen after first confirming close; stop active immediately in entryminute. Cancel if trigger is last minute or nextopen at/beyond planned stop (no positive initial risk); do not find another trigger. If later bar opens throughstop exitatworseopen; otherwise touchedstopprice; no profit target. If not stopped exitlast minuteclose. These are explicit benchmark fill/cancellation assumptions. Costs gross - .59 points per executed roundtrip;0 if no trade. Source cost=1tick eachway(.50point)+$4.50commission/$50perpoint(.09point). Not current broker fees, not calibrated variable slippage. Gaps allowed between windows, but strict within-window fullcoverage. Source complete vendor-degraded rows retained, no price repair, no duplicate timestamps; audit reports source mix/quality. No original bars published.

## Statistics and denominators

summary.csv keys family/or_minutes/atr_length/side/model/period. trades=count actual model entries in that cell, signal_days=distinct NY decision trading dates with entries. gross_avg_points=mean signed exit-entry, net_avg_points=mean(gross-.59). net_win_pct=100*count(net>0)/trades, including nonpositive results in denominator; stop_pct=100*stopped/trades. net_ci_low/high are intervals for THAT net mean per trade. No trades gives0counts and unavailable means/intervals. annual.csv uses decision trading year;2026partial; net_avg_points and trades same definitions, no inference from pooled alternatives.

paired-comparison.csv: one common strict complete/ATR-ready parent universe for each setting. If a rule has no entry, assign0points for that window; otherwise gross-.59. eligible_parents=universe count including zero-entry windows. sweep/plain_trades=count entries therein. sweep/plain_net_per_parent=sum(aftercostpoints)/eligible parents; difference=sweepminusplain perparent; difference_ci bounds estimate THAT paired per-window difference, not per-trade average. Positive difference can mean losing less, not profitable. Eligibility does not depend on future price result, but its data-completeness filter is retrospective. Median across settings in article is descriptive, not portfolio performance. Do not sum overlapping trade counts across variants.

parent-eligibility.csv: source_parents=all observed family windows, including partial4H; legacy_90pct_parents includes original quality/trade-duration gate but before ATR readiness/entry; strict_complete_parents=full duration, allminutes, single segment/contract; strict_atr9/14_eligible additionally require positive priorhistory. Covariates not optimised. Fingerprints hash rounded8decimals gross matrices (NaN represented1e12), eligible masks and stop flags in original chronological parent order/OR,ATR,side product order; no per-event values emitted. They let verifier check every strict outcome rather than only matching means.

## Periods and uncertainty

Historical 2010–2015;development 2016–2022;later 2023–Sep11,2026;allavailable overlaps them. No untouched claim: source already examined later dates. Resample whole decision dates 1000 times, each carrying sum/count for per trade or paired eligible-window average; percentile 2.5/97.5 interval. Seed first 8 bytes SHA256 of 20261020|key,little-endian; key for trade row=family|OR|ATR|side|model|period; paired=paired|family|OR|ATR|side|period. NumPy default_rng. No independent-days guarantee or multiplicity correction, nofutureprediction interval. Original saved intervals use other settings, no exact interval reproduction claim. Every year including 2020 retained; no outcomes cross their own largerwindow.

## Verification and examples

Original replay matches 288 rows / 1440 saved count/mean/win/stop metrics. Strict independent grouping, complete-parent ATR, every per-window gross outcome/stop flag/eligible mask checked through 24 matrix hashes;10128 numeric checks across 576 strict summary,2448 annual,288 pairedrows;24 selected development/later interval rows independently resampled. Other intervals use same verified formula. 12 tests cover touch ordering,entryminute stops,stop gaps,short symmetry,tickrounding,missingATR,incompletewindows,costs,Wilderseed. Source hash unchanged. Strict metrics tolerance2e-8relative/2e-7absolute, matrix grossquartertickprices exact after rounding.

Made-up example: OR high 6002, low 5998, parent open 6000, prior ATR 5; long stop 5997. Earlier post-OR low 5997.75, subsequent close 6002.25, next open 6002.50. No stop and terminal close 6006 -> gross 3.5 / net 2.91 points. No actual historical trade. Source/sweep/plain comparisons share history; no independent confirmation or live execution claim. Human review required before publishing this version.
