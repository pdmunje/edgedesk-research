# Is buying a level better than waiting for a rebound?

Prepared October 28, 2026. This is a research-methods article and a proposed test,
not an empirical backtest. Actual market observations tested: ZERO. The four
worked cases are invented fill-price arithmetic. Their relative frequency and
fill probability are unknown. They cannot establish a preferred entry rule.

## Evidence and its limits

The recovered prior discussion supplied hypotheses about entry price, waiting,
fast approaches and fills. No matched opportunity ledger, point-in-time levels,
queue observations or completed comparison was recovered for that discussion.
Earlier directional advice is not treated as a checked result. Separate level
studies may use different events, sources and rules; they are not an independent
verification of this comparison. No market study is restarted or run here.

CME's order descriptions distinguish a limit price from a stop trigger. A buy
limit caps its execution price; it does not guarantee execution. Protected market
and stop orders can leave a remainder resting at the protection limit. Our
illustrated fill prices are assumptions, not a reconstruction of that mechanism.
Sources checked October28,2026:
https://www.cmegroup.com/education/courses/futures-trading-mechanics-and-regulation/futures-order-types
https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457227032

## Distinguish the decisions

An entry condition says when a setup is allowed to enter. An execution instruction
says how the order may fill. Waiting for a completed reclaim does not specify a
buy-stop, stop-limit or protected market order. Buying a downward move in
expectation of a return is a mean-reversion idea even if entry waits for a rebound.
This article does not establish that mean reversion is superior over short horizons.

Better entry price on trades both methods take is only one part of the comparison.
A method can miss profitable opportunities, avoid losses, enter later and still
lose, or experience unfavorable movement after a passive fill. A change in fill
population means its per-filled-trade mean has a different denominator.

## Reproduce the four invented cases

examples.json explicitly supplies prices and whether each arm filled. There is
no simulated order book and no OHLC/price-path entry engine. All are one-unit long
examples, one opportunity per row. Market dates, observed sample and actual queue
likelihood: not applicable. The stipulated exits are transparent assumptions.
No original vendor data or private account observations are included.

Tick=0.25ESpoints; total round-trip cost=3ticks=0.75points per filled trade.
For each arm and case:

    if stipulated_fill:
        gross_points = exit_price - entry_price
        net_points = gross_points - 0.75
    else:
        gross_points = 0
        cost_points = 0
        net_points = 0
    paired_difference = confirmation_net - limit_net

Case Fast rebound: limit100->104 => net3.25; confirmation102->104 => net1.25.
Case Continued decline: limit100->95.5 => net-5.25; confirmation no fill =>0.
The95.5 exit stipulates a held-position gap through a96 stop, not a guaranteed fill.
Case Rebound then failure: limit100->96 =>-4.75; confirmation101.5->96 =>-6.25.
Case Touch without passive fill: passive no fill=>0; confirmation101->104=>2.25.
The last case stipulates nonfill at a touch and later filled confirmation. It does
not infer that a touch would, or would not, fill at any real exchange.

The JSON/CSV also includes illustrative totals ONLY to check denominator arithmetic:
limit net total-6.75 /4 invented opportunities=-1.6875, or /3 stipulated fills=-2.25.
Confirmation total-2.75 /4=-0.6875, or /3=-0.9166667. These are the arithmetic of
four deliberately constructed examples with equal weights, not market means or
probabilities. Do not use them to rank, calibrate or select either approach.
Changing the assumed cases or weights can change their ordering.

## Proposed matched test, not executed

protocol.json fixes a concrete FIRST comparison before any new market calculation.
These choices are deliberately arbitrary starting rules, not optimized parameters.
Changing them creates a new protocol version and must be disclosed.

One immutable long reference L per day must have been published before09:35 New
York local time, with preserved point-in-time source/version evidence. At09:35,
arm only if the completed09:34 close is strictly aboveL. One opportunity per eligible
armed day, one unit per arm, no reentry, scaling or overlapping second opportunity.
A date lacking source evidence is excluded with its reason counted.

Passive arm: buy limitL working09:35 through before09:40. Separately show a
hypothetical touch-fill rule and a penetration-required rule (low<=L-0.25). Neither
proves queue execution. Confirmation arm: within bars09:35..09:39, require a
low<=L-0.25 followed on the same or a later completed bar by close>=L+0.25.
Queue one next-minute-open buy, before09:45; cancel if the opening price is not
strictly between fixed stopL-4 and targetL+4. The last possible09:39 close can
fill at09:40. This is an explicit paper-fill convention, not a live latency claim.

Both arms keep the SAME absolute stopL-4, targetL+4 and09:45OPEN liquidation.
Consequently a later entry can have less remaining reward and more distance to
invalidation. A fixed-risk-per-entry comparison would ask a different question.
For an existing position, show observed adverse-gap stop fills with explicit cost
assumptions; do not fill every stop at its original trigger. Do not use signal-bar
extremes before entry. No new entry at09:45.

If OHLC cannot order first fill/stop/target, or a first passive fill gaps beyond
invalidation, keep that outcome UNRESOLVED. Seek finer evidence or report supported
favorable/adverse bounds. It is not a no-fill with zero result. Never silently assume
a target won. Real protected-order nonfills, quote latency, partial fills and queue
position require actual execution/order evidence and separate modeling.

Freeze approach descriptors at09:34 completed close, BEFORE either arm is allowed
to enter. Do not retroactively cancel a fill using its later touch-bar close/low.

    speed = max(0, close[t-5]-close[t]) / ATR9[t]
    efficiency = abs(close[t]-close[t-5])
                 / sum(abs(close[i]-close[i-1]),i=t-4..t)

Five one-minute changes are used. ATR9 uses Wilder true range: first TR=high-low,
then max(high-low,abs(high-prior observed close),abs(low-prior observed close));
seed first nine TRs with their mean, then(8*priorATR+TR)/9. No future bar or reset;
gaps/missing history need an explicit eligibility policy. ATR must be positive;
zero denominator makes the descriptor unavailable, not a low-confidence score.
Report speed below1.5 versus>=1.5 and efficiency below0.8 versus>=0.8 as separate
pre-entry descriptive strata. They are not a proven cancellation/trading policy.
Do not substitute the whole later decline for information available at arming.
Shorts need a separately documented mirrored protocol; none is tested here.

## What an empirical report would count

N=all eligible armed opportunities selected before outcomes are known; U=unresolved
outcomes. Keep original N and U explicit. A separately labeled resolved subset has
N-U cases and is not the full comparison. Never relabel unresolved as unfilled.
If U remains, provide supported bounds over original N or state the full mean
unidentifiable, rather than claiming a complete result.
For a complete resolved comparison:

    fill_rate = actual_filled_trades / all_eligible_armed_opportunities
    mean_per_fill = sum(net_profit) / filled_trade_count
    mean_per_opportunity = sum(net_profit) / all_eligible_armed_opportunities
    paired_difference = mean(confirmation_net - passive_net)
    winner_rate = net_winners / filled_trade_count

No fill means no position, zero trading profit and no round-trip fee, while keeping
that opportunity in the common denominator. Zero profit after costs is flat, not a
winner. A no-fill is not a loss avoided unless its comparator actually loses; it
can also miss a winner. Zero fills makes mean-per-fill/win-rate undefined.

Use costs0/1/3/5TOTALticks per filled round trip, actual observed gaps, explicit
latency and fill assumptions. Predeclare the date split before inspecting returns.
Show all frozen variants, dates, missing levels/data, contracts, source fingerprints,
fill/missed/unresolved counts, same absolute exits and all costs. Cluster repeated
observations by session/level as appropriate; do not call parameter rows independent
samples. A condition seen to work retrospectively still needs later evidence.

## Outputs and checks

reproduce.py calculates stipulated price differences and zero/fill denominators,
not the proposed market protocol. Results are illustrations.csv and
illustrative-denominators.json. verify.py uses exact Decimal arithmetic and
hand-specified outcomes. It checks53 arithmetic/boundary comparisons across the
four cases, no-fill costs, flat-gross costs, empty denominators and constant versus
one-direction approach paths. It does not test an exchange or historical engine.

    python -B reproduce.py
    python -B verify.py

Python3.12.14 standard library; no install or network is required. requirements.txt
is a comment-only record of that fact. Input hashes identify the invented examples
and proposed protocol, not vendor data or observed performance.

The Library uses its existing study-design card because there is no suitable
empirical numeric comparison. Invented arithmetic must not become market-result bars.
No original prices, account observations, raw chats, private application/card code,
machine paths or credentials belong in this research directory. Publication needs
owner review of the exact article/research/card version.
