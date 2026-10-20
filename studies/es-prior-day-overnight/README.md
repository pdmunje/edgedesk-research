# Did a down day lead to a stronger ES overnight rise?

Prepared October 15, 2026. This package is research only. The accompanying
article explains every rule without requiring code inspection.

## Result and its limits

482 eligible nights on morning dates August 30, 2024–August 28, 2026.
231 down-day nights: mean +4.699134 points, +0.0730611%.
251 flat/up-day nights: mean +2.148406 points, +0.0329253%.
Positive shares are 133/231 and 144/251. The mean percentage difference's
95% week-resampled range includes zero. Outside Sunday entries the point
difference is only +0.422683. The stricter-quality comparison reverses slightly.
This is not a validated predictive filter, causal estimate or executable account test.

## Rules

All times use America/New_York. Minute timestamps label the beginning of a bar.
Use opens, not the minute's later close. For Monday–Thursday 18:00 entries,
use that calendar day's 09:30 and 16:00 opens. For Sunday use exactly Friday.
If either required daytime price is missing, skip; do not substitute an older day.

Daytime points = open at 16:00 minus open at 09:30.
Down group: daytime points < 0. Other group: daytime points >= 0 (including flat).
Overnight points = next morning's 09:30 open minus evening's 18:00 open.
Overnight percent = 100 * overnight points / evening open.
Require all four prices from one dated contract, a 390-minute daytime interval,
a 930-minute overnight interval, and the daytime end before the evening entry.
The original session_date must equal the actual morning date.
The Friday-to-Sunday price gap is never included in a Sunday entrant's return.

Each night has equal weight. Average = sum / included night count.
Positive share = strictly positive nights / all included nights * 100; flat stays.
Median = middle sorted observation, averaging the two middle values when needed.
Net points = overnight points minus combined assumed round-trip cost.
Costs 0.5, 1, 2 and 4 points are hypothetical, not measured execution costs.
JSON `bps` means basis points: divide by 100 to get percentage returns.
Difference between two percentage returns is expressed in percentage points.

515 matching overnight pairs minus 25 missing exact daytime pairs minus 8
cross-window contract changes = 482. Full dated exclusions are in summary.json.
There are three flat daytime changes and one flat overnight in the final sample.
The prior script's date-shift grouping had different eligibility; these counts
are intentionally not forced to match its previously explored groups.

Strict diagnostic: 390 daytime observations from 09:30 through 15:59 plus
16:00 boundary, 930 overnight observations from 18:00 through 09:29; no degraded
or roll-transition flags within daytime 09:30–16:00 inclusive, and none in the
entire source-defined overnight session. It retains 421 nights (202 down, 219 other).
This uses later session flags and is retrospective, not an ex-ante entry rule.

Weeks are Monday–Sunday calendar weeks of morning dates. Resample the original
number of weeks with replacement, keep all included nights in each chosen week,
use the same weeks for both groups, compute each return sum / its own night
count and subtract means. Repeat 10,000 times, NumPy seed 20261015, report 2.5th
and 97.5th percentiles. Intervals are for historical means under this method.
They do not adjust for prior searches or dependence lasting beyond a week.
The sign split was previously explored. Later dates here are not untouched data.
Sunday stratification and quality checks are diagnostics, not new confirmations.
The older long-history candle input lacks the equivalent explicit 16:00 open;
its different daytime definition is not used as a verification of this rule.

## Licensed input, schema and fingerprint

Supply your own authorized ZIP containing exactly one CSV with these columns:

* timestamp_utc: timezone-aware UTC timestamp of minute start, strictly ordered/unique.
* session_date: YYYY-MM-DD futures-session label corresponding to morning date.
* open: finite positive price.
* underlying_contract: dated futures-contract identifier.
* data_condition: `degraded` marks a source-quality problem.
* is_complete: boolean true for every supplied row; this does not imply no absent minutes.
* roll_transition: boolean source roll flag.

Input archive: 707,321 observations, source spans August 28, 2024–August 28, 2026.
SHA-256: b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c
The script checks its fingerprint before and after calculation and fails on
duplicate timestamps, incomplete supplied bars or invalid prices. Vendor price
accuracy and the upstream contract-selection process have not been audited.
The fingerprint identifies an input; it is not a data license or download link.
No original market bars, private applications or account information are included.

## Reproduce and verify

Tested with Python 3.12.14 and pinned dependencies in requirements.txt.
Run from this directory, supplying a path to your licensed input:

```text
python -m pip install -r requirements.txt
python -B reproduce.py --input YOUR_LICENSED_ARCHIVE.zip --output output
python -B verify.py --input YOUR_LICENSED_ARCHIVE.zip --summary output/summary.json --output output/verification.json
```

Outputs are aggregate JSON/CSV only. No extracted vendor data is written.
`verify.py` independently parses rows with the standard-library CSV reader,
pairs overnight timestamps by adding 930 minutes, looks up daytime dates and
recounts descriptive results without calling the production calculation.
Its nine made-up tests also exercise production mechanics on temporary fake bars.
378 numerical comparisons passed. This is not a separate audit of vendor
prices or an independent bootstrap implementation. Temporary fake inputs are
deleted automatically and contain no source observations.

## Files and change history

* reproduce.py: focused portable calculation.
* verify.py: independent descriptive recount and nine made-up tests.
* requirements.txt: pinned runtime dependencies.
* results/summary.json: complete aggregates, exclusions, resampling settings.
* results/annual_summary.csv: calendar-year counts, means, positive counts.
* results/verification.json: actual checked values and scope.

October 15, 2026: initial research draft, exact calendar mapping and matching
contract requirements replace the older observed-row shift. Previously explored
quartile boundaries are not promoted into a validated signal. No human approval
is asserted by this calculation record; the owner reviews the exact version in Studio.
