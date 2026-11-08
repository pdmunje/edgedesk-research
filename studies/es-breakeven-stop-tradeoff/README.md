# When does moving a stop to the entry price help or hurt?

Prepared October 29, 2026. Fresh matched-entry reconstruction on an old saved price/
Buy FVG file. Not exact reproduction of prior code, validation of the indicator,
a live execution study or an independently validated strategy.

## Main result

All 18 target/path/management means are negative after an illustrative three-tick
TOTAL round-trip cost. The high-based +16 tick trigger changes the 32 target mean by
-0.194444 ticks/trade under the low-first path and +0.100000 under high-first.
Both resulting net means remain negative. For 96 target it changes the mean by
-3.411111 ticks over 90 matched entries and -3.336957 over 92, respectively.
Close-based activation is worse than the fixed stop for all 6 path/target ledgers.

Low-first 32/64/96 fixed-stop trade counts 108/96/90 have net 3 means
-2.787037/-3.802083/-1.444444 ticks. The high-trigger entry-stop versions have
-2.981481/-3.854167/-4.855556; close-trigger versions-4.111111/-4.270833/-5.311111.
All zero/negative rows and the full high-first scenario remain in summary.csv.

For low-first 96, the high-trigger version has 55 gross-zero outcomes out of 90,
but 82/90 net losers after 3 ticks. One entry-stop opening gap loses before costs.
It improves 36 trades, worsens 19 and leaves 35 unchanged. Twelve of the baseline's
18 target exits become entry-stop exits;35 baseline losers become exact price-flat
outcomes. These are conditional retrospective counts, not entry-time predictions.

## Authorized input and dates

Provide an authorized identical one-minute CSV. SHA 256:
6e27d99f34e299896d2273199d7bdcf9c07ba1009e3ce76df5493e00e94b0918
Required columns:time, open, high, low, close, Buy FVG. Extra columns do not participate.
Time is timezone-aware ISO text; prices are ES points. Require ordered unique
minute-start timestamps and positive finite quarter-point OHLC with low<=open/
close<=high. Require positive quarter-point FVG values when present. Blank,
nonfinite, nonpositive or unparsable FVG is unavailable, not zero or forward-filled.
A fingerprint identifies a file; it does not grant a license or supply a download.

The file has 20, 460 rows from June 28, 2026 18:00 through July 17 16:59 New York time.
There are 21 unavailable saved FVG values and 36 rows unavailable after the one-bar
reference lag/gap gate, across the WHOLE file, not counts of excluded sessions.
Eighteen observed local dates are candidate daytime windows. Four lack an 08:35
or 15:55 boundary:June 28, July 3, July 5, July 12. Fourteen complete windows remain,
June 29 through July 17. Every eligible window has the 440 intervening one-minute
steps and 441 rows including its cutoff open. No missing price/minute is filled.
The selection is full-window historical coverage, not a real-time missing-feed rule.

Use America/New_York clock time, not fixed EST. All these dates are summer EDT.
Window starts 08:35; ends at 15:55 OPEN. Include price paths 08:35..15:54, not 15:55
high/low/close. The old 15:54 close and our 15:55 open are distinct fill conventions.
No new entry at 15:55; no overnight or outside-window positions are modeled.

## Signals and the fixed-stop entry ledger

At each completed bar t, reference=Buy FVG from preceding consecutive one-minute
row t-1. No carry across a timestamp gap. Each close compares to its OWN prior-row
reference, not one unchanged line shared by five bars. The series can move.
All streaks reset at window start, unavailable reference or a close>=reference.
Counts continue while holding, but only flat bars can arm a new order.

    if reference exists and close[t] < reference[t]: streak += 1
    else: streak = 0
    if flat and streak >= 5 and next open is BEFORE 15:55:
        one-bar buy stop = reference[t]  # known saved prior-row value

The earliest entry is 08:40 after 08:35..08:39 complete. A pending order is active
only on the next bar and is consumed/cancelled there. If not filled and five-below
still holds at its close, issue a fresh one-bar order at the latest reference.
There is at most one trade at a time and no second entry within one bar.
At an entry-bar open>=trigger fill at that observed open; otherwise on an upward
path crossing fill the trigger. Stop=entry TRIGGER minus 32 ticks, frozen thereafter.
Target=actual fill plus 32/64/96 ticks. A gap above the trigger can make initial
entry-to-stop risk larger than 32 ticks;32 below a reference is not a guaranteed
maximum trade loss. Target fills at target with no favorable opening improvement.

The baseline fixed-stop simulation defines its OWN nonoverlapping entry schedule
for each target/path pair. Replay both managed variants on EXACTLY those entry
bars, phases, trigger prices and fills. If a managed exit occurs earlier, it stays
flat until the next baseline-scheduled entry; no extra early reentries are allowed.
Therefore every paired row has the same filled-entry denominator. This isolates
exit management, not a full strategy that reuses every earlier freed signal.
Different targets or paths can produce different baseline entry schedules. Do not
pool their trade counts or interpret them as paired fills across scenarios.

## Intrabar assumptions and execution

The minute record does not reveal whether its high or low came first. Retain TWO
specified continuous piecewise-linear scenarios for EVERY bar:
1.open->low->high->close (low_first)
2.open->high->low->close (high_first)
Neither is observed truth, a probability-weighted estimate or a rigorous performance
bound. Other compatible paths can differ. Do not select a path by candle color or
pick whichever delivers a winner. Entry and exits follow the chosen ordered path;
exclude vertices before an intrabar buy stop actually crosses. For example, a
low-first low below an initial stop before the rising entry is not a stopped trade.
An existing position may hit stop and target in the same bar; path order decides.

At every later open, apply any pending stop raise, then check the active stop.
If open<stop, exit at observed open (adverse gap); if open==stop, exact touch.
Otherwise if open>=target, exit at target. At cutoff, close any remaining position
at that open and ignore later cutoff-bar extremes. Observed open fills and path
crossings are paper assumptions; they do not reconstruct protected-order nonfills,
partial fills, quote latency, queue position or actual broker execution.

## The two stop-raising conditions

Initial stop is frozen trigger-32 ticks. If still holding at a completed close:
* High rule: post-entry high within that completed bar>=actual entry+16 ticks.
* Close rule: completed close>=actual entry+16 ticks.

One qualifying completed bar is enough. It means a bar reached the threshold,
not that every moment or the whole following minute was profitable. Entry-bar
movement before the actual fill is excluded. A target/stop exit earlier in the
bar closes the trade and cannot cause a later raise.

If qualified, raise stop to exact ENTRY starting at NEXT bar's open. Do not use
that new stop retroactively within the confirmation bar. Once active it never
moves down. At next open below entry, exit at that lower observed open. The stop
can also first become active at the final cutoff open; stop-gap logic precedes
the fallback time-exit classification there.

Made-up example, not market input: buy 5000, trigger 5000, initial stop 4992,
32 tick target 5008. A completed bar reaches 5004 (+16 ticks) but closes 5002.
High rule arms; close rule does not. No new stop existed during that bar.
Next open 4999.25 gives an entry-stop exit at 4999.25, gross-3 ticks and net-6 ticks
with a 3 tick total cost. If it instead exits exactly 5000, gross 0 and net-3 ticks.

## Statistics, costs and denominators

Tick=.25 points. Gross ticks=exit_ticks-entry_ticks. Net=gross-cost_total_ticks.
Illustrative costs 0/1/3/5 ticks are combined round-trip fees/friction, charged ONCE
per filled trade including time exits. They are not actual broker quotes or
measured slippage. Gap price movement is already in the modeled gross fill.

Means=sum/all filled matched entries; median=middle sorted outcomes (mean of two
middle if even). Winner>0, loser<0, flat=0 after the indicated cost. Gross-zero
includes ANY exact price-flat outcome, including a time exit; entry-stop exits
instead classify the order that caused an exit, including adverse gaps. The counts
must not be equated. Stop-raised trades count activation even if exit is at target
or cutoff. Target+fixed-stop+entry-stop+time-exit categories partition all trades;
entry-stop-gap is a subset of entry-stop exits. Net winners/losers/flats partition
all trades after 3 ticks. No-trade session rows stay in sessions.csv as zeros.
Empty means are undefined, not profit or flat-trade claims.

Paired change=managed gross minus fixed gross for SAME entry; net change is the
same here because both pay the SAME per-trade total cost. Report improved>0,
worse<0, unchanged=0, each over all matched entries. Total change/count=mean change.
Conditional loss-to-flat and target-to-entry-stop counts are descriptive after
both replays finish, not signals available beforehand. One ES point=4 ticks.
No R multiple, account percentage, sizing, margin, compounding, maximum adverse
excursion or account drawdown is claimed. Worst realized loss in this small modeled
sample is not a risk bound, particularly when a later open can gap through a stop.

## Relation to prior work and exclusions

The old narrative reported 139/137/133 breakeven trades and called the 32 target
substantially improved. That compared changing trade schedules and did not recover
the original code/events. Those results are NOT claimed exactly reproduced here.
This reconstruction uses a prior-row saved reference, explicit intrabar paths,
matched fixed-stop entry schedules and 15:55 open closure. It does not establish the
original Buy FVG construction, first live availability, lack of repainting or
contract adjustment/roll truth. A one-row lag cannot repair historical repainting.
No later-date validation is included. No new target, trigger or stop search is run.
The same June-July file appears in the seven-level study; it is overlapping source
evidence, not independent confirmation of entry quality. Daytime/Buy FVG events
here differ from the seven-level count signals.

## Outputs and reproduction

summary.csv:18 rows=2 paths*3 targets*3 policies, including all costs, outcome counts,
exit causes, worst realized trade and complete ordered event fingerprints.
paired-comparison.csv:12 matched changes=2 paths*3 targets*2 managed variants.
sessions.csv:252 rows=14 dates*18 variants, preserving no-trade dates.
eligibility.csv:18 observed date candidates and first exclusion reason.
audit.json:source fingerprint/dates/missing values and limitations.
verification.json:actual checks. Individual source bars, levels and fill logs excluded.

    python -m pip install -r requirements.txt
    python -B reproduce.py --input YOUR_AUTHORIZED_EXPORT.csv
    python -B verify.py --input YOUR_AUTHORIZED_EXPORT.csv

Tested Python 3.12.14 and tzdata 2026.5. Production follows each ordered path segment
and a chronological pending-order/position loop. The verifier independently scans
five-bar candidates, reconstructs first exits from range/path order and separately
checks numeric summaries, paired changes and all session rows. Source parser/window
selection and the digest routine are shared. Fifteen invented mechanics groups,
1, 010 numeric checks and all 18 full event fingerprints agree. These checks verify
implementation agreement on stated assumptions, not real fills or future edge.

No original data, raw chats, account observations, machine paths, credentials or
private application/card code belong in this research-only directory. The owner
reviews the exact article/files/card version before publication.
