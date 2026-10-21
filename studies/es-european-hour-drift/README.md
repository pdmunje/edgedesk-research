# Did ES rise between 2 and 3 a.m. New York time?

Prepared October 15, 2026. Research-only calculation package.

## Question, answer and overlap

516 eligible one-hour observations on August 29, 2024–August 28, 2026.
Mean movement +0.4907946 points (+0.0071467%); median +0.5 points;
267 positive / 516 = 51.7442%, with eight flat observations.
A hypothetical 0.5-point combined entry-and-exit cost leaves -0.0092054 mean
net points. The overall week-resampled 95% mean range includes zero.
The partial 2024 group is negative; the partial 2026 group is stronger.
The stricter 506-hour sample averages +0.5148221 points before costs,
which is also essentially zero after the same half-point assumption.
This does not establish an executable or dependable trading edge.

This hour was previously explored within the same overnight archive. It is not
an unseen test or independent confirmation. The shared-date comparison uses
514 observations also having matching 18:00 and following 09:30 prices.
Full overnight mean points = one-hour mean points + remaining overnight mean
points on those same dates. The remainder combines 18:00–02:00 and 03:00–09:30;
it is price arithmetic, not a costed two-trade strategy.
No external paper is replicated or used as confirmation.

## Exact formulas, timing and units

Convert each UTC timestamp to America/New_York using IANA timezone rules.
Use the 02:00 minute open and 03:00 minute open on the same actual local date.
Require each boundary exactly once, matching source session date, same dated
contract and exactly 60 elapsed UTC minutes. Missing boundaries are not filled.
No 18:00 or 09:30 price is needed for the main one-hour sample.
Winter entries appear at 07:00 UTC (175 observations); daylight-time entries
at 06:00 UTC (341). Every actual retained hour is on a Monday–Friday date;
none lands on a Sunday clock change. This is a fixed New York window,
not a constant European local opening time or an externally validated mechanism.

Points = 03:00 open - 02:00 open.
Percent = 100 * points / 02:00 open.
Net points = points - assumed combined entry-and-exit cost.
Mean = sum / eligible one-hour pair count, equal weight per pair.
Positive share = strictly positive movements / all pairs * 100.
Net-positive share = movements > cost / all pairs * 100.
Median = middle sorted value, average of two middle values when needed.
Flat observations stay in all percentage denominators.
JSON bps means basis points: divide by 100 for percentage returns.
Each percentage uses its own entry price; do not divide mean points by mean price.
Mean ranges are calculated separately in points and basis points.

Hypothetical costs are 0.5, 1, 2 and 4 points per round trip. They are not broker
quotes or measured spread/slippage. Constant point costs subtract the same
amount from the point mean and both mean-range endpoints. A positive price
change is not a verified filled/profitable trade. No stops, targets, sizing,
reinvestment, margin, financing or within-hour maximum losses are modeled.

## Eligibility and quality

Source has 707,321 rows and 518 session dates. Initial 2024-08-28 fragment
and 2025-11-28 have no 02:00 entry. Other 516 dates have matching 03:00 prices,
same contracts and 60-minute elapsed times; no candidate is rejected otherwise.
The main sample retains flags and absent intermediate minutes.

Strict diagnostic requires 60 observed minutes 02:00 through 02:59, separate
03:00 open, one dated contract throughout, and no degraded/roll-transition flag
within 02:00 through 03:00 inclusive. It retains 506 observations. Four others
have 59 interior minutes; six are source-flagged; none has an interior contract
change. Exact dates and reasons are in results/summary.json. This uses data
through the exit minute and is retrospective, not an ex-ante entry rule.

Two main-sample dates, 2025-01-09 and 2026-04-03, lack the full overnight's
09:30 exit but have valid one-hour prices. Keep them for the main hour question.
The original overnight-constrained breakdown had 514 observations instead;
its six descriptive aggregates match the fresh calculation on those shared dates.
An initial fragment is not an inferred full-day trade opportunity. Supplied bars
marked complete do not imply all expected minutes exist. Vendor recording and
upstream contract selection have not been independently audited.

## Uncertainty and earlier/later checks

Group observations by the Monday–Sunday calendar week of the actual hour date.
Draw the same number of observed weeks with replacement; keep all included
observations in each selected week. For each draw, divide movement sum by the
sampled observation count. Repeat 10,000 times, NumPy seed 20261015; use 2.5th
and 97.5th percentiles. These are weekly block bootstrap ranges for means,
not future individual returns or probabilities of successful trading.
They do not correct for prior time-window searches or dependence beyond a week.
Annual groups use actual hour dates; 2024 and 2026 are partial years.
Earlier/later groups split at 2025-08-29, each containing 258 observations.
Both were already explored; the later year is not a holdout.

## Licensed input and schema

Obtain your own authorized ZIP with exactly one CSV containing:

* timestamp_utc: timezone-aware minute-start time, ordered and unique.
* session_date: YYYY-MM-DD source futures-session/morning date.
* open: finite positive price.
* underlying_contract: dated futures-contract identifier.
* data_condition: `degraded` identifies a source-quality problem.
* is_complete: boolean true on every supplied source record.
* roll_transition: boolean source contract-roll marker.

Archive source range: August 28, 2024–August 28, 2026.
SHA-256: b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c
Fingerprint is checked before and after calculation. Duplicate timestamps,
duplicate boundaries, incomplete supplied bars or invalid prices cause failure.
The fingerprint identifies the input, not a license or public download route.
No original vendor records or private application files are distributed.

## Reproduction and verification

Tested with Python 3.12.14; install pinned dependencies from requirements.txt.
Run from this study directory, supplying your own permitted input:

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_LICENSED_ARCHIVE.zip --output output
python -B verify.py --input YOUR_LICENSED_ARCHIVE.zip --summary output/summary.json --output output/verification.json
```

The optional verification flag `--baseline ORIGINAL_AGGREGATE.json` checks six
shared-date values against an earlier saved overnight-study summary containing
`european_hour_bps`. It is not required to reproduce any new calculation.
Without that optional file, the baseline match count is zero; all source recount
and mechanics checks still run. The saved verification record includes that
extra check from the original private provenance; no private paths are retained.

The separate standard-library CSV parser recounts source time conversion,
boundary pairing, quality and descriptive aggregates. 192 numerical comparisons
and 12 made-up tests passed. Six shared-date descriptive values matched the older
saved result. Bootstrap intervals are not independently implemented, although
constant cost shifts are checked. Vendor prices are not independently audited.
Temporary fixtures contain invented observations and are removed automatically.

## Files, changes and approval

* reproduce.py: standalone focused calculation, aggregate outputs only.
* verify.py: independent source recount and made-up timing/quality tests.
* requirements.txt: pinned numpy, pandas and tzdata.
* results/summary.json: full aggregates, quality exclusions and method settings.
* results/annual_summary.csv: annual observation counts, means and positive counts.
* results/verification.json: actual checks and limits.

October 15, 2026: first draft, standalone one-hour sample and separately labeled
514-date overnight overlap. Daylight saving, costs and weak earlier periods are
explicit. No human approval is inferred from successful calculations. The owner
reviews the exact version in Studio before publication.
