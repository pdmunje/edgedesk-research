# Fixed ES overnight return study

Question: did an evening-to-morning long position have a positive historical average after assumed costs?

For each eligible source-defined futures session, subtract the 18:00 New York minute open from the following 09:30 minute open. Both observations must exist and have the same underlying dated contract. The source timestamps identify minute starts. One observation is one night; there is no stop, target or sizing rule. Missing endpoints are never replaced. Percentage return is 100 times (exit / entry minus 1).

The mean gives each eligible night equal weight. Positive-night percentages include zero results in the denominator, but count only strictly positive results in the numerator. Net points subtract a fixed round-trip cost once per night: 0.5, 1.0 or 2.0 points, equivalent to 2, 4 or 8 ticks. These are assumptions, not broker quotes.

The 95% mean intervals resample complete ISO calendar weeks of exit-session dates with replacement, 20,000 times, seed 20261010. Each draw includes as many weeks as the source sample has, and its mean weights the drawn nights equally. Adding a constant cost subtracts that same cost from both interval endpoints. Intervals are estimates under this resampling scheme, not guarantees about future trading or individual nights.

## Source and input schema

The licensed archive has SHA-256 `b9e1acf1ee029db919e6e5feba38bd985d06a84af8193c11ce93722606c6356c`. It contains exactly one CSV member. It has 707,321 completed rows, beginning 2024-08-28 20:59 UTC and ending 2026-08-28 20:59 UTC. Session dates span 518 dates, including an initial fragment. There are 517 evening-entry references and 515 eligible pairs; exit dates run from 2024-08-29 through 2026-08-28.

Required columns: `timestamp_utc` (timezone-aware minute-start time), `session_date` (futures-session exit date), `open`, `high`, `low`, `close`, `underlying_contract`, `data_condition`, `quality_flag`, `is_complete`, `roll_transition`. Preserve original vendor quality and contract metadata. Boolean fields accept true/false. Price fields are unadjusted dated-contract prices. The program rejects duplicate timestamps, incomplete bars or duplicate overnight boundary bars rather than inventing a new policy.

The main endpoint sample retains missing intermediate minutes and source-quality flags when the exact same-contract boundary prices are available. The stricter sensitivity sample requires 930 observed overnight minutes, no degraded-data flag anywhere in the source session and no roll flag anywhere in that session. It contains 444 nights. Quality exclusions are retrospective research checks, not signals presumed known at entry.

The attached data is summarized only. Obtain permitted licensed input independently; the input archive is not included or redistributable through this package. A different source file or different contract/session convention can produce different results. The checksum identifies the input; it does not establish public availability or licensing rights.

## Reproduce

Use Python 3.12 with the pinned versions in `requirements.txt` and working America/New_York timezone data. The verification run used the bundled environment's timezone database. On systems without IANA timezones, provision the standard timezone database before running.

```text
python -m pip install -r requirements.txt
python reproduce.py --input /your/licensed/dataset.zip --output-dir rebuilt-results
```

`base_analysis.py` retains the earlier source calculation, with only its private fixed input path and printed-result delivery replaced. `reproduce.py` supplies the input, verifies duplicate/completion rules, hashes the input before and after, and independently recounts overnight results using Python's CSV parser and arithmetic rather than the pandas pivot used by the source study. The original source rerun and portable output matched every original results section.

## Output and limits

`results/summary.json` holds the complete source-study aggregate results plus the fingerprint and shifted cost intervals. `results/verification.json` records the actual checks. No raw minute bars or endpoint prices are exported. The full summary includes the earlier weekday, prior-day, monthly and one-hour exploratory breakdowns for transparency. Those additional hypotheses were not independently verified as trading edges in this article. Their naive t statistics are retained as source output, but the article relies on the week-resampled intervals instead.

This is not a compounded account backtest. No stops, intranight maximum losses, margin, drawdown or actual fills are modelled. These dates were already explored and are not a fresh holdout. Other queued overnight and gap articles overlap them and are not independent confirmations. Never infer stop-based strategy profit or a guaranteed fill from endpoint return alone.

## Change and approval record

October 15, 2026: source rerun, portable reproduction, independent CSV recount and first private article draft. Calculation checks passed. Human publication approval is pending; no public push was performed. The exact research commit is attached by Studio only after the owner reviews and publishes this version.
