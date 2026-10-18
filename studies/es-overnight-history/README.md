# How did ES overnight returns change since 2000?

Reproducible research support for an EdgeDesk article. The owner reviews the exact article/package version before publication. Original vendor prices are not distributed.

## Question and measurement

This is a descriptive study of an owner-obtained continuous ES chart export. Continuous means successive futures contracts have been joined into a historical series. Its upstream contract-selection and price-adjustment settings have not been recovered. Do not describe these bars as verified unadjusted same-contract trade prices.

Select a row only when it starts at exactly 18:00 America/New_York, the immediately following row starts at 09:30, and those starts are exactly 930 elapsed minutes apart. The evening row's closing price is the primary endpoint. The following row's opening price is a separate sensitivity check. They are not assumed equal.

```text
for each row and the immediately following row:
    if row begins at 18:00 New York time
       and following row begins at 09:30
       and following time - row time is exactly 930 minutes:
        morning_date = following row's New York calendar date
        points = evening row close - evening row open
        percentage = 100 * points / evening row open
        basis_points = 10000 * points / evening row open
    otherwise:
        exclude this evening candidate
```

One basis point is 0.01%; 100 basis points are 1%. The mean gives every eligible night equal weight, and is not a compounded account return. The median is the middle result after sorting (average the two middle values for an even count). Positive-night share counts strictly positive results divided by all eligible nights, including flat nights. Candle returns describe a long-direction price change without a stop, target or position-sizing rule; a close is not an executable fill guarantee.

## Periods and costs

Use morning dates to form these existing exploratory groups: 2000–2010, 2011–2020, 2021–2023, and January 2024–October 5, 2026. The boundaries were chosen in the earlier analysis after the data was available. They are descriptive historical slices, not rules learned before an independent test. The final two groups are shorter than the earlier groups. Annual results are also saved to avoid hiding variation within each group.

Hypothetical round-trip costs are 0.5, 1.0 and 2.0 price points, subtracted once per eligible night:

```text
net_points = close - open - assumed_cost_points
net_percentage = 100 * net_points / open
mean_net_percentage = sum(each night's net_percentage) / number_of_nights
```

Costs are illustrative combined execution/fee assumptions, not historical broker quotes. A fixed point cost uses a larger percentage of an earlier, lower index price. Therefore do not subtract an average point cost from a percentage return, or assume average points and average percentages must have the same sign. No dollar account return, margin rule, compounding or changing fee history is modeled.

## Mean uncertainty ranges

For each displayed group independently, label observations by the ISO calendar week of the morning date. Keep every night within a week together. Sample that group's original number of weeks with replacement, sum sampled returns and divide by the sampled number of nights. Repeat 5,000 times using NumPy's default random generator, seed 20261015. The 2.5th and 97.5th percentiles of the resampled means form the displayed 95% range.

This is a weekly block bootstrap, meaning nearby nights in a selected week are resampled together. These ranges concern a historical average under that procedure; they are not the range containing 95% of individual nights, a forecast, or a probability of a profitable next trade. They do not account for selection of the historical boundaries, dependencies beyond a week or market changes. This follow-up uses consistent within-group resampling rather than copying the old intervals. No formal test that one period's true average differs from another is claimed.

## Inputs and exclusions

Required historical CSV columns: `time` (ISO timestamp with a UTC offset), `open`, `close` (finite numeric prices, open positive). Extra columns such as high, low and volume are ignored. Rows must be strictly time-ordered and unique. Convert timestamps to America/New_York for the checks; use UTC for elapsed time. Input SHA-256:

`4b9faa5ea1ab8377f209d22630d959c75bb1ad2e265c61023aa08d3b89339b6d`

The source has 13,809 rows, including 6,825 rows starting at 18:00 and 6,984 rows at other times. Of 6,825 evening candidates, nine are followed by a different start time and one final row has no following row. The remaining 6,815 eligible overnight bars end on morning dates January 3, 2000 through October 5, 2026. This checks timestamp boundaries; it does not establish complete minute-by-minute coverage within each candle. No holiday schedule or missing observations are fabricated.

Excluded evening dates: June 10, 2004; April 29, 2010; April 5, 2012; April 2, 2015; December 4, 2018; April 1, 2021; April 6, 2023; January 8, 2025; April 2, 2026; and October 5, 2026. The last is the unfinished evening row, not the eligible overnight candle ending that same morning. The first nine fail the following-row start-time check. These are source-boundary exclusions, not a claim about their economic or holiday causes.

The input has no underlying-contract identifiers, roll flags or minute-quality flags. We cannot reproduce the minute study's stricter quality exclusions or validate older roll treatment from this file. The fingerprint identifies the exact private input; it does not establish public availability or redistribution rights. Acquire permitted source data independently for reproduction.

## Comparison with the minute-data study

The separate licensed one-minute ZIP must contain exactly one CSV with `timestamp_utc`, `session_date`, `open`, and `underlying_contract`. Timestamps are timezone-aware minute starts; `session_date` labels the futures trading date including its preceding evening. There must be at most one 18:00 and one 09:30 opening observation per date. Archive SHA-256:

`b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`

Compare the historical candle's close-minus-open change with the minute source's 09:30-open-minus-18:00-open change on matched dates only. Save differences, counts and fingerprints without distributing prices. This comparison covers 515 nights, August 29, 2024–August 28, 2026. It is the previous overnight article's endpoint sample, not its 444-night stricter subset. It is neither independent evidence for those same dates nor an audit of 2000–2024 prices. The script records whether the minute endpoints have different dated contracts rather than silently treating them as interchangeable.

## Made-up example

If an evening candle opens at 5,000 and closes at 5,005, its movement is +5 points or +0.1% (10 basis points). If the next daytime candle opens at 5,005.25, the alternative endpoint movement is +5.25 points or +0.105%. A one-point assumed round-trip cost gives +4 net points or +0.08% using the original candle close. These prices are illustrative, not observations from the study.

## Reproduce and verify

Verified environment: Python 3.12.14 with the pinned dependencies in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input /path/to/continuous-es-930m.csv --minute-input /path/to/licensed-es-minute.zip --output output
python -B verify.py --input /path/to/continuous-es-930m.csv --summary output/summary.json --output output/verification.json
```

The calculation writes aggregate `summary.json` and `period_summary.csv` only. It reads original files without altering them. The verifier uses Python's CSV reader, standard-library dates and arithmetic to pair and recount the historical bars without importing the analysis's pandas implementation. Its six made-up tests cover endpoint differences, interrupted candles, elapsed time, an unfinished last row, zero-return denominators and duplicate-time rejection. It does not independently validate vendor prices, the source comparison or bootstrap ranges. The recorded verification also notes comparisons with the freshly rerun earlier analysis. Code, assumptions and summarized results are the public research package; the original CSV/ZIP files remain private.

## What the output fields mean

- `all_history`, `periods`, `by_year`: first/last observed morning date, eligible-night count, point and basis-point summaries, and historical mean range.
- `close_vs_next_open`: exact-equality counts and alternative endpoint summaries. Equality uses exact numeric differences, not an unspecified price tolerance.
- `cost_scenarios_all_history`, `recent_cost_scenarios`: hypothetical net results, with the cost applied separately to each night's entry price.
- `overlap_with_minute_source`: aggregate cross-source differences on their shared dates.
- `period_summary.csv`: one row for each of the four periods; return columns labelled `bps` are basis points, not percentages. Divide them by 100 to obtain percentage units.

This historical description retains the negative 2021–2023 result and the cost-sensitive all-history result. It does not establish a durable profitable rule or future return.
