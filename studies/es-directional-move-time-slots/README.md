# When does ES confirm a sustained move—and how much is already over?

Prepared November 5, 2026. Event study pending specific-version owner review.

## Finding

Across 44,655 retained qualifying runs, mean whole observed move=32.554831 ticks; already completed at recognition=25.216706; remaining to observed run end=7.338126. Median remaining=0. There was no additional observed same-colour bar in 25,060/44,655=56.12%. These are retrospective marks, not executable returns.

09:00–10:00 New York has the highest eligible-hour confirmation frequency both before 2020 (1,111/1,893=58.69%) and from2020 (1,118/1,720=65%). All observed clock groups are retained. An earlier source ranked different-length windows on an unrecovered ten-minute export; this does not reproduce its event sizes or old winning window. This is a new declared reconstruction on an already explored licensed minute archive.

## Input and strict construction

Supply the separately licensed ES Parquet with SHA-256:
2a794cbeae8f8fc3022d4079e98c32e8d9dc030ba1d1bda2b457aa857f0fa6f9

Required fields: timestamp_utc (timezone-aware ordered unique UTC minute opening), open/high/low/close (finite positive internally valid OHLC), underlying_contract, roll_transition, is_complete, quality_state, price_source. Source contract choice and vendor correctness are not independently rebuilt. Missing fingerprint/schema/price/timestamp contracts fail; no data is downloaded or redistributed.

Raw 4,931,583 rows: 2010-06-06T22:00Z through 2026-09-11T00:19Z. Exclude 347 complete rows at local 17:00–18:00 and 1,400 rows with unknown contract identity, leaving 4,929,836 minutes. Known-identity data ends 2026-09-09T23:59Z. Retained labels: 4,906,274 certified and 23,562 vendor_degraded; these are source labels, not a new certification. All 65 original roll flags define segments before filtering; adjacent known identity changes must have a roll flag. Do not guess missing contracts or change the input archive.

Group on exact ten-minute UTC buckets (whole-hour New York offsets keep local ten-minute alignment). Require ten distinct consecutive minute openings, first at bucket start and last nine minutes later, all in one segment. Open=first, high=max, low=min, close=last. Of 497,799 observed groups, 19,851 fail, leaving 477,948 complete ten-minute bars. Entire missing groups are not invented or counted as observed failures. Keep exact source values; no price rounding.

## Exact event and availability rules

Green: close>open; red: close<open; equality is a doji and breaks a run. A run is the maximal observed same-colour sequence, reset at gap, roll, opposite colour, doji or file edge. Ten-minute True Range=max(high-low,abs(high-prior close),abs(low-prior close)); it needs a preceding contiguous bar. Large=current TR>=2*arithmetic mean(previous six completed valid TRs). Current range is excluded from that reference; equality qualifies. No Wilder averaging. Reset at gaps/rolls, requiring seven preceding uninterrupted bars for six valid prior TRs and their prior close.

Recognize once: at the second completed close if the first two bars are large; otherwise at the third completed same-colour close, if present. A two-bar run without a large pair does not qualify. All longer runs are counted once. Source response supplied the two/three thresholds; this reconstruction freezes them without searching new lengths or claiming they are optimal.

Recognition time=qualifying bar opening+10 minutes. It is not the earlier opening label. Direction d=+1 green, -1 red. ES ticks use 0.25 index point:

    whole_ticks = d*(last run close-first run open)/.25
    completed_ticks = d*(recognition close-first run open)/.25
    remaining_ticks = d*(last run close-recognition close)/.25
    whole = completed + remaining

Library values use ES points=ticks/4. All three component rows have the same 44,655-run denominator; total and parts are not independent groups. Invented example: initial open 100, completed green closes 101/102/103 without an early large pair recognizes at 103. If it ends there, whole 12 ticks=completed 12+remaining 0. A fourth green close 104 gives 16=12+4. Invented ranges 6 for each of six prior bars make current TR 12 qualify and 11.75 fail.

## Equal hour exposure and two periods

Assign each event to the clock hour containing its recognition timestamp, exactly 10:00 belongs 10:00–11:00. This is recognition time, not run-start time. The full observed run may start before/end after its assigned hour. Eligible hour=six exact complete ten-minute bars from the same contract segment covering that whole UTC hour, labelled in America/New_York. Frequency=hours with>=1 recognition/eligible hours. Multiple recognitions in an hour mean event count differs from hour count; events per 100 hours can exceed 100. No frequency*whole-size expected-profit claim.

73,516 eligible hour windows remain; 9,571 observed hour groups fail. Detector finds 46,754 runs; 2,099 confirmations lack a complete eligible hour and are excluded, leaving 44,655. Excluded events are not counted as zero moves. Complete-hour eligibility is retrospective and can change session coverage. No 17:00–18:00 windows remain; before 2020, 16:00–17:00 has no complete windows under this grid and is explicitly not measured. No exchange-calendar diagnosis is invented for each gap.

Trading-date label=local date+1 if hour >= 18, otherwise local date. Split confirmation-hour trading dates before 2020-01-01 versus2020 onward. Both periods reuse previously examined history; no untouched validation. All 68 observed hour/period rows and nine event/period rows are saved. Two disjoint run classes: 438 two-bar large pairs and 44,217 runs with>=3 same-colour bars. Larger runs containing large pairs are not counted again.

## Limits and interpretation

265 retained runs end at a data/session/roll boundary or file edge. No unobserved future colour is inferred. Observed end-of-run marks are hindsight: the final same-colour close is only identified after a subsequent opposite/doji bar or boundary. Even remaining movement is not executable trade expectancy. No entry/exit order, stop, target, latency, spread, liquidity, commission, slippage, sizing, equity or drawdown is modeled. A cost haircut cannot turn descriptive hindsight into a fill backtest.

Events share market days, prices and regimes. Tick sizes can change with price level/volatility across periods. Searching clock groups can favor historical winners; no independent-trial interval, significance or future probability is established. This relates to momentum persistence and calendar returns but measures a different event; shared archive history is not independent confirmation.

## Reproduce and verify

Checked with Python 3.13.15; dependencies pinned in requirements.txt: numpy 2.3.5, pandas 2.3.3, pyarrow 21.0.0, pytz 2026.3.post1.

    python -m pip install -r requirements.txt
    python reproduce.py --input YOUR_LICENSED_ES.parquet --private-cache YOUR_PRIVATE_CACHE
    python verify.py --input YOUR_LICENSED_ES.parquet --private-cache YOUR_PRIVATE_CACHE

Calculator writes only aggregate results.json, event-summary.csv and hour-summary.csv publicly. The required cache holds vendor-derived bars/events and must remain outside this study/repository. Never distribute it. Verifier uses no object deserialization: independent reduce-at aggregation checks 1,911,792 OHLC values; scalar prior-TR loop checks 477,948 large labels; causal streaming recognizer verifies all 46,754 confirmations and 44,655 supported runs without future-run-end knowledge at recognition; nine event and 68 hour summary rows recounted; three invented mechanics checks pass. verification.json records actual checks.

CME tick reference, checked November 5, 2026: https://www.cmegroup.com/education/courses/introduction-to-equity-index-products/discover-equity-index-notional-value-and-price . No source indicator, original chart archive, raw chats, vendor rows, private application/card code, machine paths or credentials are redistributed.

Change history: November 5, 2026 — explicit long-history reconstruction and missing-identity exclusion, complete-hour comparisons, independent checks and private article/card prepared. Human publication approval remains pending.
