# Correct direction versus a losing simulated trade

Archive-only companion to the Kronos verdict, using the same saved historical forecasts. Owner closure October 22,2026 remains in force. No models or services are started.

## Reproduction

Python 3.13.15; numpy 2.3.5; pandas 2.3.3 (requirements.txt). No inference package or network needed.

```
python reproduce.py --input YOUR_LICENSED_SNAPSHOT.csv
python verify.py --input YOUR_LICENSED_SNAPSHOT.csv --reference YOUR_FROZEN_HISTORY_SUMMARY.csv
```

Input SHA-256: `6d14f9b278472669891d6c9e20d8076ed00407a44d6f552919477d86108f077b`,18,201,198bytes. Schema: symbol/model/lookback/variant/target_date/phase; previous_close,predicted_close,actual_open,actual_close; stored bias,gross_usd,cost_usd,net_usd for reconciliation. Unique market/model/input/seed/date key. Finite prices. Reference is frozen history_by_seed.csv; checked fields days,direction_days,direction_correct,flat_actual_days,trades,no_trade_days,winners,losers,breakeven. Original prices and individual forecast/outcome rows remain private; exact reproduction requires matching lawful inputs.

History July 2,2025–October 16,2026;43098 rows. Exclude 132 October 19 historical-extension and 264 October 20–21 prospective rows. ES/NQ have 327 market dates;GC/CL 326 (April 3,2026 absent for those two). Eleven settings per market and 3 seeds reuse dates. Not 43098 independent days.

## Formulas and classification

b=sign(predicted close-previous close), a=sign(actual close-previous close). Correct direction means a!=0 and b==a. Trade points=b*(close-open). Signed close-to-close points=b*(close-previous close); signed gap=b*(open-previous close). Trade points=close-to-close points-signed gap. Previous close is attribution, never an assumed tradable fill.

Gross USD=round(trade points*multiplier,2). Cost=5+2*tick*multiplier if b!=0, else 0. Net=round(gross-cost,2). Archived specs: ES(.25,50),NQ(.25,20),GC(.1,100),CL(.01,1000); corresponding round-trip costs 30/15/25/25 USD. One standard contract enters at the stored target open and exits at its close. These are assumed marks and costs, not current broker quotes or guaranteed fills.

Disjoint direction groups: correct nonflat, incorrect nonflat, actual-flat. Outcomes: entered net win(>0),net loss(<0),entered breakeven(==0),no trade(b==0,cost 0). Direction accuracy excludes actual-flat days; flat predictions on nonflat days count as wrong. Trades retain actual-flat days. No-trade cases are excluded from entered-trade win-rate denominators. No no-trade or entered-breakeven rows happened in this retained sample.

Correct-loss share=net-losing rows with correct nonflat sign / all correct nonflat sign rows. Correctness is retrospective, not a known entry filter. Correct-loss causes: negative gross, zero gross, positive gross below costs; mutually exclusive and summing to all correct losses.

## Findings and limits

1882/21283 correct-direction rows lose after costs;1743 negative gross,59 zero gross,80 positive gross below costs. There are 1875 incorrect-nonflat direction rows with positive net trades. Direction denominator 42999;actual-flat 99 retained in 43098 trade rows. All counts include repeated seeds/settings, not independent trials. No new rule is validated and no brokerage execution/account return is established.

Independent scalar checks:43098 identities/arithmetic,132 archive count matches,4 market summaries,12 cohort rows,partition reconciliation,2 unchanged source fingerprints,4 invented mechanics cases. Original vendor minute coverage, rolls, model timing/pretraining and executable fills are inherited or unverified. No intraday drawdown,capital,margin,position sizing or compounding. Related articles share the same archive.

Files: README.md,config.json,requirements.txt,reproduce.py,verify.py,results.json,series.csv,cohorts.csv,markets.csv,verification.json.
