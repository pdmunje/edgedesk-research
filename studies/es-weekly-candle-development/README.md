# Does a green start to an ES week mean more gains are still ahead?

Prepared November 3, 2026. Descriptive recheck of previously explored inputs.
No executable strategy, actual fill, unused-date validation or future probability
is established. Research files contain summarized output only.

## Question and main finding

After a green D1 (first stored daily session), 448/695 = 64.46% of weeks finish
above the weekly open. Only 364/695 = 52.37% finish above the D1 close. The mean
whole-week change is +15.981151 points, but +16.401942 points are already completed.
The mean still ahead is -0.420791 points. The next-open-to-final-close mean is
-1.138633 points. The whole-week color and later price movement answer different
questions.

After four green daily sessions, 101/101 weeks finish green but only 59/101 finish
above D4 close. These are old selected observations, not a guaranteed signal.
The report retains all observed prefixes, ties, baselines and weak/negative results.

## Inputs and reproduction

Python 3.12.14 standard library suffices for the main calculation and independent
checker. requirements.txt intentionally adds no runtime package. Supply identical
lawfully available CSVs, each with time, open, high, low and close columns. Dates
are ISO YYYY-MM-DD labels, prices are positive ES points; volume/extra columns
are unused. The hashes below identify files, not a data download or license:

Daily SHA-256:
aa50dad895c5698ae35e24333cf093b682736a4d8477e53563ca7607ef7037eb

Weekly SHA-256:
7532b21c4307c79e4bcac9598e5611e37d8109d1dd737a13e73950bfbf5bccfc

    python -B reproduce.py --daily YOUR_AUTHORIZED_DAILY.csv --weekly YOUR_AUTHORIZED_WEEKLY.csv
    python -B verify.py --daily YOUR_AUTHORIZED_DAILY.csv --weekly YOUR_AUTHORIZED_WEEKLY.csv

Raw data, individual weekly prices and event-level records are excluded. Input
fingerprint mismatch stops reproduction instead of silently using different data.

## Calendar grouping, exact reconciliation and eligibility

Both files have date-only labels. Define calendar-week key = labelled date minus
weekday number (Monday=0, Tuesday=1). Apply this to BOTH daily and weekly exports.
Eighty-eight weekly labels are Tuesdays, so direct Monday-date equality would fail.
Require a unique weekly record for each normalized week and exactly the same keys.

Within each group, preserve the original chronological daily rows:

    weekly open  = first daily open
    weekly high  = maximum daily high
    weekly low   = minimum daily low
    weekly close = final daily close

Require exact Decimal equality for every OHLC field. All 1,504 supplied weekly
records match. No missing date or price is filled, no row is rounded and no week
is merged across a calendar boundary. OHLC is open/high/low/close.

Primary eligibility = exactly five supplied daily rows in the calendar group.
D1-D5 mean first through fifth stored session, rather than an assumed weekday.
All eligible full-history rows happen to carry Monday-Friday labels; exchange
session start/close and active trading hours are not proven by date labels.

Daily file: 7,285 rows, September 9, 1997 through June 30, 2026.
Weekly file: 1,504 rows, September 8, 1997 through June 29, 2026.
Primary: 1,274 weeks, Monday keys September 15, 1997 through June 22, 2026,
with final included daily label June 26, 2026.
Excluded other-count weeks: 230 = 227 four-row + one three-row + two two-row weeks.
These include source-boundary and shortened weeks; no calendar proves every one
is a holiday. Five stored bars also do not prove five full-length sessions.

The five-row rule is retrospective. It is not known at D1 merely because the week
later qualifies. A live strategy needs an at-the-time eligible-week rule, suitable
calendar/coverage evidence, verified completion timestamps and fill modeling.
Neither the whole-week selection nor the reference changes provide those guarantees.

## Color conditions and outcomes

    G: daily close > its own open
    R: daily close < its own open
    D: daily close == its own open exactly (doji)

A length-k prefix concatenates the first k daily colors for k=1,2,3,4. GG does
not require successively higher closes: daily opens can gap. Prefixes that do not
occur are absent, not 0% outcomes. Stage five has no remaining week to predict.

    green final week: final close > first open
    remaining up: final close > session-k close
    next-open up: final close > session-(k+1) open
    next-day green: session-(k+1) close > its own open

These are separate comparisons. Red/down and exact tie categories are kept too.
Every percentage denominator is ALL selected weeks, including exact ties.
The whole-week baseline is 711 green / 1,274 weeks = 55.808477%, with 558 red
and five doji weeks. No target-doji exclusion is used in this study.

## Exact movement definitions and means

    whole_week_points = final close - first open
    elapsed_points    = session-k close - first open
    remaining_points  = final close - session-k close
    next_open_points  = final close - session-(k+1) open

    whole_week_points = elapsed_points + remaining_points (every week)
    remaining_pct = 100 * remaining_points / session-k close
    next_open_pct = 100 * next_open_points / session-(k+1) open

Means sum individual measurements and divide by selected-week count. Medians
sort individual measurements and take the middle, averaging two middle values
for an even count. Percentage means average each week's own percentage.
An ES point is a price unit, not an account percentage return. Exact equal-price
outcomes contribute zero to means and remain in share denominators.

Illustrative invented prices, not market data: open=100, D1 close=110, next
open=111, final close=105. Whole week=+5, elapsed=+10, remaining=-5, next-open=-6.
A green week can therefore contain negative movement after a completed condition.
The verifier checks this invented arithmetic with a five-session fixture.

Same-close and next-open marks do not prove actionability or fill availability.
There are no orders, positions, trading costs, slippage, stops, sizing, account
returns, drawdown or short-side reversal backtest. Exact exchange completion and
order latency are unverified. A positive chart change is not net trading profit.

## Baselines and repeated searches

ALL means no prefix requirement within that stage/period. Use its own-stage
remaining-close or next-open outcome as the appropriate comparison. Do not use
50% or the whole-week green baseline as an interchangeable future-window baseline.
Each of the four stages reuses the same eligible weeks but measures a different
remaining interval. Prefixes partition weeks within one stage, not across stages.

Full history has 82 observed prefixes: 3 length-one, 9 length-two, 23 length-three
and 47 length-four. The uniform green/red examples were selected because the old
study highlighted them, not as newly discovered best parameters. All 195 summary
rows across full, 2010-onward and 2020-onward periods remain in summary.csv.
The latter periods have 715 and 279 weeks, filtered by the Monday key's year.
These nested, previously inspected dates are NOT unused validation samples.
No significance, confidence interval, multiple-search correction or calibrated
future success probability is claimed. A count >=50 is not a reliability guarantee.

## First high/low timing

For each eligible week, find the maximum of daily highs and minimum of daily lows.
Assign each final extreme to its FIRST matching session. There are 34 tied-high
weeks and 21 tied-low weeks; earliest ties keep the five session counts disjoint.
Each set of high counts and low counts sums to 1,274. A week can contribute its
high and low to different sessions. At-the-time knowledge of a final extreme is
not inferred. D5 high first: 458/1,274 =35.949765%. D1 low first:405/1,274=31.789639%.
These are retrospective descriptions, not entry-success probabilities.

## Verification and limited archived comparison

verify.py has its own Decimal loader, ISO-week grouping, prefix selection, median,
percentage arithmetic and ordered calendar-key hashes. It checks 5,470 numerical
and event values across 195 summaries, 12 stage-period partitions, exact OHLC
agreement for all 1,504 weeks and seven boundary groups. Production functions are
called only by the added made-up fixtures, not the full-data reconciliation.

The saved workbook comparison covers all 82 length-1 through length-4 prefix
counts, final-green shares and mean whole-week points, plus ten first-high/low
percentages. All match. It does not certify the workbook's other factors, exact
five-session patterns, cumulative paths, inference or full search history.

Optional archive comparison requires your authorized identical workbook and
openpyxl 3.1.5 (read-only). Its SHA-256 is recorded in config.json.

    python -m pip install openpyxl==3.1.5
    python -B check_archive.py --workbook YOUR_AUTHORIZED_PROFILE_WORKBOOK.xlsx

Saved output: results/archive-reconciliation.json. This is a count/mean audit,
not a claim that the old workbook or a model conclusion validates a live strategy.

## Output files and limits

summary.csv retains counts, percentages, full/elapsed/remaining/next-open means,
medians, next-day colors and ordered event fingerprints. Event hashes identify a
selection without distributing its underlying price rows. high-low-timing.csv
contains summarized first-extreme counts. audit.json records dates, exclusions,
ties and price-grid anomalies. verification.json records actual independent checks.

Four daily and two weekly rows contain a non-quarter-point OHLC price. Original
values are preserved. Vendor continuous-contract construction, adjustment/roll
policy, older history construction, exact completion and holiday durations are
unverified. Matching supplied files is not independent certification of market
truth. Point and volatility scales change across decades; percentage summaries
and medians remain available. No untouched later file is supplied or invented.

This study overlaps daily-decline and session-transition research dates. Weekly
prefixes describe a different event but do not create independent confirmation.
All code and summaries here are research-only. Raw vendor rows, individual prices,
private app/card code, chats, credentials, account information and machine paths
remain excluded. Publication requires owner review of the matching article/card/files.
