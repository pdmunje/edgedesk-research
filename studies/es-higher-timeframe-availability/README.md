# When can a one-minute backtest use an hourly signal?

Prepared November 3, 2026. This is a methods demonstration. ALL dates, source
values, delays, IDs, sessions and counts are invented teaching inputs. No market
prices, historical ES signals, trades, private feature snapshots or similarity
results are included. The examples do not certify a production implementation.

## Main point

A completed source value must be complete and legally available by the decision
time. Its historical presence does not establish earlier availability. Carrying
one completed source update onto later minute rows retains the original source
identity; it does not manufacture additional source updates.

The inspected source specifies identity, completion-time and repeated-pair rules.
It is a requirements record, not an audited implementation result. No source
instruction to run a separate private research stage is executed by this package.

## Reproduce

Python 3.12.14, standard library only. No packages, market files, feed, credentials,
model download or protected source are needed.

    python -B reproduce.py
    python -B verify.py

illustration.json is the complete invented input. config.json pins its SHA-256
and the exact counting/timing policy. requirements.txt adds no dependencies.
The dated examples use January 6, 2026 with a fixed -05:00 UTC offset. This is
not a derived exchange-session or daylight-saving calendar. Equivalent explicit
UTC timestamps are checked. All time comparisons use aware datetime objects.

## Three clocks and separate execution

source_start is the source candle's opening label. completed_at is its specified
end. known_at is the first time this finished calculated value is available.
The example requires known_at >= completed_at. A delayed receipt/calculation can
therefore prevent use even though the source is complete.

    completion <= decision
    known_at <= decision < valid_until

valid_until is an explicit input contract, exclusive at its boundary. It is not
an invented universal one-hour expiry policy. Real features need their accepted
carry, freshness, session and warm-up definitions. This package does not repair
or modify any private engine's policy.

Calculation eligibility is not an order or fill. A complete real test must model
receipt/calculation, decision, order transmission and the subsequent fill rule.
A value first known at 10:00:02 cannot justify a fill at the earlier 10:00 open.
No price or fill modeling, trading costs, positions, profit, return or drawdown
is computed here.

## Exact selector

Each invented observation has feature, session, observation_id, source_start,
completed_at, known_at, valid_until, value and mode. An optional ambiguity flag
marks unresolved completion metadata.

1. Reject developing mode in this completed-mode selector.
2. Reject missing or ambiguous completion, or missing availability.
3. Reject invalid source/known-time order and nonpositive validity interval.
4. At decision T, retain only complete, known and unexpired source observations.
5. Select the latest completed_at, then latest known_at, among those observations.
6. If several identities still tie, mark unavailable instead of choosing arbitrarily.
7. If the selected latest value is null, retain its ID with MISSING_VALUE. Do not
   replace it with an older non-null value.
8. Keep valid Boolean False and numeric 0 as their actual distinct values.

Duplicate feature/session/source-ID identities stop the teaching program. All
fixture sources belong to one invented session. This selector is not a general
multi-instrument or multi-session production adapter. The repeated-pair key does
include session so records from different sessions are not collapsed.

Missing/ambiguous time is excluded with a reason. Never infer completion from
value presence, overwrite unknown completion with a base/minute timestamp, use
nearest-future matching or forward-fill before legal availability. An older
observation may carry only while its OWN accepted interval remains valid, retaining
its original identity and age. Developing snapshots require their own time-valid
definition and stored inputs; a final candle cannot substitute for them afterward.

## Boundary and missing-state examples

H0 is complete/available at 09:00, valid until 10:00, value False. H1 belongs to
09:00-10:00, is complete/available at 10:00, valid until 11:00, value True.
H2 is complete/available at 11:00, valid until 12:00, value False.

    09:59:59.999: H1 unavailable; existing H0 still valid
    10:00:00.000: H1 eligible, given its known_at == 10:00 contract
    10:00:00.001: the SAME H1, not a fresh hourly update
    08:59:59.999: no eligible previous observation
    12:00:00.000: H2 expired; no new value is assumed

The separate L1 completes at 10:00 but known_at is 10:00:02. It stays unavailable
until that later boundary. The two-second delay is invented, not measured latency.

U1 has missing completion, A1 ambiguous completion, K1 missing known time, and D1
is developing. These are four metadata exclusions. M1 has known/complete timing
but a missing value and retains its selected ID. Z1 is a valid numeric zero.
H0's Boolean False is valid too. All 18 exact decisions are in decision-checks.csv.
The value column uses JSON text: null, false, true and 0 stay distinguishable.

## Identity and repeated views

For the source's registered intrabar records, identity is base_bar_id plus the
registered HTF filter. Uniqueness does not prove availability. A completed source
carried into a minute view keeps its original completed-source ID; a viewer
minute does not replace it. Different IDs with equal values stay different updates.

The source feature-comparison rule retains BOTH source identities:

    key = session_id + source_observation_id_A + source_observation_id_B
    sort eligible decision rows by timestamp
    keep earliest eligible row per key

Report displayed rows, A updates, B updates, distinct pairs and sessions separately.
Source-pair counts are not an estimate of independent trials. Consecutive updates
may share inputs, price windows and market conditions. Dependence and uncertainty
require further treatment for the specific question.

If minute exposure is the intended quantity, time weighting can be intentional.
If the intended quantity is source-update comparison, repeated minute rows change
its weighting. Neither silently substitutes for the other. Neither turns each
minute display into an independent trade or outcome.

## Invented weighting arithmetic

P has one constant True source update. Q has a True update followed by a False
update. Their two source pairs comprise one match and one disagreement.

One view per pair:

    displayed agreement = 1 / 2 = 50%
    distinct-pair agreement = 1 / 2 = 50%
    distinct P updates = 1; distinct Q updates = 2

Sixty views of the matching pair, then one of the other:

    displayed agreement = 60 / 61 = 98.3606557377%
    distinct-pair agreement = 1 / 2 = 50%
    distinct P updates = 1; distinct Q updates = 2

The second schedule repeats actual calculated selections at 10:00 through 10:59
and at 11:00 in the invented clock. Q0 expires at 11:00; Q1 becomes available then.
All pair selections satisfy the teaching timing contract before counting.
This is an arithmetic comparison only. A constant P does not provide an ordinary
correlation or a feature-quality test. No private similarity metric, threshold,
qualification, pruning recommendation, trading edge or future probability follows.

## Verification and files

verify.py checks 18 rows against explicit expected identities, statuses and typed
values. Independent Fraction arithmetic checks both repeated-view count panels.
There are 76 explicit output/fraction comparisons and 15 property-test groups,
recorded in results/verification.json. Properties include exact boundaries, delayed
availability, equivalent UTC clocks, future-value changes not changing past
selection, source reorder invariance, latest missing-value preservation, False/0,
expiry, duplicate IDs, unresolved latest-ID ties and invalid/offset-free times.
Distinct-pair checks preserve earliest time, retain equal-valued different IDs,
retain session identity and resist display repetition.

results/decision-checks.csv holds 18 invented decisions; exclusions.csv holds the
four source-metadata reasons. repetition-summary.csv holds the two count panels.
audit.json records scope and input hash. No raw vendor data or private source
checkpoint is used. Research-only code, invented inputs and summarized results
remain separate from website/card code.

## Limits and related research

These tests establish the stated example contract only. They do not prove feed
truth, actual delivery latency, exchange boundaries, real warm-up behavior,
protected-checkpoint integrity, historical signal availability, statistical
independence, prediction accuracy or executable performance.

This complements checking a fixed signal less frequently: schedule controls WHEN
a decision changes, while availability controls WHAT it may know at that time.
It also complements overlapping-minute research: repeated source displays differ
from overlapping future-return windows. Removing one duplicate type does not
solve the other or establish independence.

No historical market sample, new probability estimate or unused-date validation is
claimed. No engine, strategy, collector, schedule or protected inputs are changed.
Publication requires owner review of the matching article, existing study-design
card and this research-only package. Raw chats, vendor rows, private application
code, machine paths, credentials and account information are excluded.
