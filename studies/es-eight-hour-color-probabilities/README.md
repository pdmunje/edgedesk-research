# Does the same eight-hour ES condition work in every candle slot?

Prepared October 30, 2026. This is a focused descriptive recheck of previously
explored historical data, not a new strategy, a full reproduction of the earlier
search, or unused-date validation. No trade fills or account results are modeled.

## Finding

In the primary 2010-onward period, three completed red candles precede a green
C1 evening target in 240 / 390 cases = 61.5385%, compared with its own baseline
2,206 / 4,145 = 53.2207%. The difference is +8.3177 percentage points. C2 is
199 / 375 = 53.0667% versus 53.5613% (−0.4946 points); C3 is 196 / 371 = 52.8302%
versus 55.7187% (−2.8885 points). A condition pooled across the whole day can
therefore obscure differences between target slots.

These counts do not establish a reliable probability for the next occurrence.
They come from reused dates and previously explored conditions. All eight
conditions, three targets and overlapping date ranges remain in summary.csv.
No statistical significance, calibrated probability or profitable rule is claimed.

## Input, license and data handling

Supply the identical authorized CSV with columns time, open, high, low, close.
Extra columns such as Volume are ignored. Prices are ES points. Time is an
ISO timestamp with its New York offset. The file fingerprint is:

2c403934eceb01b5615e99c8b2ab01461c075ff09e41a537c32b7d0e9803344d

A fingerprint does not grant a license or provide market data. The package contains
no source bars or individual target prices. It needs Python 3.12.14; Windows uses
the pinned tzdata 2026.5 database for America/New_York.

The input has 20,486 rows, January 3, 2000 at 02:00 through June 30, 2026 at 10:00
New York time. Require ordered unique aware timestamps, expected local start
hours 18/02/10, positive finite prices and valid low <= open/close <= high.
Eleven rows have a saved OHLC value outside the usual quarter-point grid; retain
it unchanged rather than rounding. Continuous-contract settings, rolls and exact
aggregate closing times are unverified. No missing row or holiday bar is created.

## Slots, trading dates and outcome timing

C1 starts 18:00; C2 starts 02:00; C3 starts 10:00, all New York local time.
Nominal successive chart boundaries are 02:00, 10:00 and 18:00. Those labels do
not imply eight uninterrupted exchange trading hours. Retain the vendor's
shortened/holiday aggregates. The export has 6,842 assigned trading dates:
6,807 with three rows and 35 incomplete. A valid pair on an incomplete date
remains eligible; do not remove the entire date automatically.

Assign an 18:00 row to the following calendar date. Other rows retain their date.
Use ADJACENT stored predictor and target rows. Accept:

- C1 -> C2, same assigned trading date.
- C2 -> C3, same assigned trading date.
- C3 -> adjacent next observed C1, including weekend/holiday gaps.

Reject all other transitions. Never skip a row to find a preferred target.
Exclude an accepted target if its close equals its open exactly. Green means
close > its own open; red means close < its own open. Predictor dojis remain
possible but fail a required red/green sequence. Last row has no following target.

There are 20,485 adjacent pairs: 34 irregular transitions rejected and 399 accepted
exact-doji targets excluded, leaving 20,052 valid non-doji outcomes. These are
full-file counts. There is no separate holiday result or live feed-gap policy.

Select periods by predictor timestamp year >= 2000, 2010 or 2020. All end at the
same export endpoint; these periods overlap. A year-boundary target follows its
predictor's period assignment. No dates after the old export are tested.

## Eight exact completed conditions

All use the completed predictor t and earlier saved rows only. Prior observations
may span calendar gaps or irregular transitions. These are stored-row sequences,
not a claim of uninterrupted clock-time exposure.

1. Current red: close[t] < open[t].
2. Current green: close[t] > open[t].
3. Three red: each of t−2, t−1, t has close < its own open.
4. Three green: each of those three has close > its own open.
5. Five lower-low moves: low[j] < low[j−1] for j=t−4,...,t.
6. Five higher-high moves: high[j] > high[j−1] over the same five comparisons.
7. Cross above SMA20: close[t] > SMA20[t] and close[t−1] <= SMA20[t−1].
8. Cross below SMA20: close[t] < SMA20[t] and close[t−1] >= SMA20[t−1].

SMA20[t] = sum of close[t−19] through close[t], divided by 20.
Five strict low/high moves need SIX rows; ties break the sequence. This explicit
convention is not a claim that the old program used the same length convention.
Three-color rules need three rows. A crossing needs 21 rows: two complete rolling
windows. Unavailable history is excluded from that condition AND its baseline,
not converted to a false signal. All primary-period rows have these histories.

## Definitions and interpretation

Each summary row has one period, one target slot and one condition.

    n = all matching non-doji targets
    green = number closing above their own opens
    red = n − green
    green_pct = 100 * green / n
    red_pct = 100 * red / n
    baseline_n = all same-slot/period non-doji targets with this condition available
    baseline_green_pct = 100 * baseline_green / baseline_n
    green_change_pp = green_pct − baseline_green_pct
    target body points = target close − target open

A percentage point is the difference between two percentages, not an investment
return. For red, subtract green percentage from 100; the red change has the opposite
sign. A below_50 flag marks a small condition sample without hiding it. Fifty was
an inherited display convention, not a guarantee of reliability.

Means sum all matching target bodies and divide by n. Median is the middle sorted
body, or average of the two middle bodies for even n. C1/C2/C3 three-red primary
means are +1.9372/+0.0560/+1.2999 ES points, with medians +1.75/+1.00/+1.25.
Candle color and chart-body size need not tell the same story. Neither is a
verified execution result. No fee, slippage, entry, position, stop, sizing,
exposure, drawdown or account-return calculation is made.

Invented arithmetic example: predictor open/close pairs 100/99, 99/98, 98/97
satisfy three red. If the last is C3, an adjacent C1 open 97.25 / close 98 is one
green target and +0.75 chart-body points. An equal open/close target is excluded
from color denominators. These invented prices are not market observations.

## Prior searching and overlap

The recovered original single-condition workbook lists 521 names and 486 eligible
unique primary-period tests. Definitions, methodology and search audits were read;
original executable code, intermediate masks and complete selection history were
not recovered. The later workbook expands selected pairs into adaptive three-to-
five-condition candidates. This recheck does NOT reproduce or certify their
p-values, corrections or rankings. A correction over just the eight choices here
would not account for the earlier search, so no fresh statistical-discovery claim
is made. Repeated sequences and conditions can select overlapping dependent dates.

The 2020 period is inside the 2010 period, itself inside full history; they are not
three independent tests. Related daily and seven-hour studies reuse market dates.
No independent confirmation of the original research or an unseen-date strategy
edge follows from this article. Freeze a specific target, condition and full test
family before any separately authorized confirmatory study.

## Files and checks

- config.json: exact input hash, period cutoffs and full condition list.
- reproduce.py: independent of spreadsheet software, parses and summarizes input.
- verify.py: Decimal/vector implementation checks all 81 rows with 972 numeric/
  event-fingerprint checks, plus 12 invented mechanics assertions. It also checks
  all nine baseline numerator/denominator pairs against the recovered workbook.
- results/summary.csv: 3 periods * 3 targets * (8 conditions + baseline) = 81 rows.
- results/audit.json: file coverage, exclusions and explicit scope limits.
- results/verification.json: actual verifier result.

Event fingerprints hash chosen source-row indices, not publish individual rows.
The independent full-file check has its own parser, masks, transition filter and
summary arithmetic; only the mechanics fixtures additionally call production
functions. Checks establish agreement on these stated rules, not vendor truth,
corrected full-search inference, actual fills or future trading value.

    python -m pip install -r requirements.txt
    python -B reproduce.py --input YOUR_AUTHORIZED_EXPORT.csv
    python -B verify.py --input YOUR_AUTHORIZED_EXPORT.csv

Original vendor data, raw chats, machine paths, credentials, individual target
prices and private website/card code remain excluded. Publication requires owner
review of the matching article, files and card version.
