# Were Sunday-night ES returns stronger than other nights?

This package supports a private EdgeDesk research draft. Only the owner approves publication of a specific article version. The calculations describe historical observations, not guaranteed executable trades.

## Question and exact rules

ES means E-mini S&P 500 futures. Compare the actual Sunday 18:00 New York entry with the Monday 09:30 exit against the other observed weekday overnights. Both prices are the opening prices of one-minute candles, usable at the timestamp identifying the start of each minute.

```text
for each source-defined futures session:
    require exactly one 18:00 minute open and one 09:30 minute open
    require both endpoints use the same dated futures contract
    require exit timestamp - entry timestamp = 930 elapsed minutes
    require actual morning date = source session date

    points = morning open - evening open
    percentage = 100 * points / evening open
    basis_points = 10000 * points / evening open

    if actual evening weekday is Sunday:
        require actual morning weekday is Monday
        assign to Sunday-entry group
    otherwise:
        require evening weekday is Monday, Tuesday, Wednesday or Thursday
        assign to pooled other-night group
```

One basis point is 0.01%. UTC instants determine elapsed time; America/New_York determines clock and weekday labels. Source session dates are checked, not assumed to imply an actual Sunday entry. Friday-evening entries are not created. The gap from Friday's close to Sunday's reopen is not part of this measured return: the entry is at the Sunday open, after that weekend gap.

One observation is one eligible night. There are no targets, stops, position sizing or reinvestment rules. Mean = sum of observations / number of observations. Median = middle ordered observation (average the middle two for even counts). Positive share = strictly positive observations / all observations, including zero, times 100. Other nights are pooled observation by observation; they are not an equal-weight average of four weekday averages.

## Inputs and source handling

The licensed minute ZIP must contain exactly one CSV with these columns:

| Column | Meaning |
|---|---|
| timestamp_utc | Timezone-aware UTC minute-start timestamp |
| session_date | Futures trading date, including its preceding evening |
| open | Finite positive original unadjusted dated-contract price |
| underlying_contract | Actual selected dated futures contract |
| data_condition | Source data condition; `degraded` is used in the sensitivity exclusion |
| is_complete | Boolean confirming the one-minute candle is complete |
| roll_transition | Boolean marking the first row after selected-contract change |

Input SHA-256: `b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`.

The archive contains 707,321 rows and 518 source session dates, including an initial fragment without an evening-entry candidate. All observed bars are marked complete. There are 517 evening-entry candidates; two have no matching 09:30 exit, labelled January 9, 2025 and April 3, 2026 by morning date. There are no mismatched endpoint contracts or wrong elapsed times among the remaining pairs. The main sample is 515 nights, morning dates August 29, 2024 through August 28, 2026: 104 Sunday entries and 411 other entries. No missing price is filled or inferred.

The main comparison retains a night when its required matching endpoint prices exist, even if other minutes are missing or the source marks part of that session degraded. The stricter check requires exactly 930 observed overnight minute bars, no degraded observation anywhere in that futures session, and no roll transition anywhere in it. It retains 444 nights: 89 Sunday and 355 other entries. These full-session quality exclusions are retrospective research diagnostics, not filters assumed known at the Sunday entry.

## Costs and example

The same round-trip costs of 0.5, 1.0, 2.0 and 4.0 points are separately tested for both groups. Subtract once per night, then convert to percentage using that night's entry price. Costs are illustrative combined fee/execution assumptions. They are not quotes, observed Sunday spreads or a calibrated model of the reopen. A larger Sunday-specific cost can be assessed by comparing its appropriate scenario with a different other-night scenario; this is still hypothetical.

```text
net_points = morning open - evening open - assumed_cost_points
net_percentage = 100 * net_points / evening open
```

Made-up example: a Sunday entry at 6,000 and Monday exit at 6,006 gives +6 points or +0.1% before costs. With a 2-point round-trip cost, the result is +4 points or approximately +0.0667%. The earlier Friday close is not used in either calculation. These are illustrative prices, not source observations.

## Uncertainty and exploratory selection

Group observations by Monday–Sunday calendar week of actual morning date, including only observed nights. Draw the original number of observed weeks with replacement, using the same selected weeks for Sunday and other groups. For each draw, sum each group's returns and divide by its own sampled night count. Save the difference between those two means. Repeat 10,000 times with NumPy default generator seed 20261015. Report the 2.5th and 97.5th percentiles for group averages and their difference.

This weekly block bootstrap retains some short-run dependence and the paired weekly comparison. It does not adjust for selecting Sunday after looking at weekday results, examining other conditions in the same sample, or trying different historical boundaries. The ranges estimate uncertainty in a historical mean under this procedure. They are not individual-night prediction ranges, probabilities of profit or proof of a future trading advantage. The new intervals are recalculated rather than copied from the source study's 20,000-draw intervals with a different seed.

Annual summaries and all five observed entry weekdays are retained. A separate diagnostic removes the five Sunday nights with the largest absolute percentage moves, then recounts the remaining 99. That deletion uses outcomes known only afterward, can remove gains and losses, and is not a tradable filter. None of these overlapping checks is independent confirmation.

## Longer-history comparison

The second input is the owner-obtained continuous ES 930-minute chart CSV, with `time`, `open`, `close`. Times are ISO timestamps with offsets; rows must be strictly ordered and unique. Prices must be finite, opens positive. Its fingerprint is:

`4b9faa5ea1ab8377f209d22630d959c75bb1ad2e265c61023aa08d3b89339b6d`

Select an evening row only if it starts at 18:00, its immediately following row starts at 09:30, and those starts are exactly 930 minutes apart. Use the evening row's close minus open, not the next daytime row's open. Check actual entry weekdays. This selects 6,815 candles ending on morning dates January 3, 2000–October 5, 2026. There are 6,825 evening candidates: nine fail the next-row clock check and the last has no following row. Matching boundaries do not certify every constituent minute.

The four existing exploratory groups use morning dates: 2000–2010, 2011–2020, 2021–2023 and January 2024–October 5, 2026. They were chosen after the data was available. Apply the same Sunday/other comparison and within-period weekly resampling. The CSV lacks contract identifiers and minute-quality flags; the upstream contract-joining and price-adjustment rules remain unverified. Its endpoint and source differ from the minute study, so do not silently merge their observations.

The 515 recent minute-study dates also occur in the historical file. Their separate comparison is labelled `historical_overlap_same_515_dates`; it is a source cross-check on the same nights, not 515 additional observations. Agreement there cannot validate the older series or prove a persistent Sunday advantage. The 2021–2023 negative Sunday result and weak earlier differences are retained.

## Reproduction

Verified environment: Python 3.12.14 and the pinned packages in `requirements.txt`.

```sh
python -m pip install -r requirements.txt
python -B reproduce.py --input /path/to/licensed-minute.zip --history-input /path/to/continuous-es-930m.csv --output output
python -B verify.py --input /path/to/licensed-minute.zip --history-input /path/to/continuous-es-930m.csv --summary output/summary.json --output output/verification.json
```

Optional `verify.py --baseline /path/to/original-minute-summary.json` compares 24 descriptive values with the first study's freshly rerun output. Verification uses a separate CSV parser, date pairing and standard-library arithmetic; it does not independently audit vendor prices or the historical mean intervals. Seven made-up checks cover calendar labels, missing endpoints, elapsed time, contract mismatch, zero denominators, unequal group weights and constant paired bootstrap differences. Temporary made-up fixtures are confined to the supplied output directory and removed after the checks.

The calculation reads and hashes both inputs before and after without modifying them. Only aggregate `summary.json` and `annual_summary.csv` are written. No original prices, per-night vendor outputs, private machine paths or application code are included in the research package. Source fingerprints identify exact files; they do not provide those files or licensing rights. Independently obtained inputs may produce different results.

## Output fields

- `main`, `stricter`: Sunday/other point and basis-point statistics with explicit night counts; `uncertainty` holds historical mean and difference ranges.
- `costs_points_per_night`: hypothetical net statistics for each assumed cost and each group.
- `all_entry_weekdays`: all five observed entry weekdays, rather than only the selected comparison.
- `minute_by_year`, `annual_summary.csv`: morning-year results; 2024 and 2026 are partial years. `bps` columns are basis points; divide by 100 to get percentage units.
- `historical_periods`: descriptive long-candle comparisons, with a different endpoint and unverified continuous-series construction.
- `remove_five_largest_absolute_sunday_moves`: retrospective outlier diagnostic, not an entry rule.
- `verification.json`: actual independent recount and mechanics-check record.

October 15, 2026: fresh source calculations, separate recount and initial private draft. Historical overlap, exploratory selection and execution-data gaps are disclosed. Publication approval is not inferred from calculation checks; the owner reviews the specific version in Studio.
