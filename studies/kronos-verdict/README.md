# Kronos daily experiment: an archive-only verdict

This package recalculates saved forecasts. It does not load models, make predictions, start services or change the closed project. Owner closure: October 22, 2026. New article preparation: November 5, 2026.

## Reproduce the analysis

Use Python 3.13.15 with numpy 2.3.5 and pandas 2.3.3 (requirements.txt). No torch, API key or model runtime is needed.

```
python reproduce.py --input YOUR_LICENSED_SNAPSHOT.csv --timing YOUR_PRIVATE_TIMING.json
python verify.py --input YOUR_LICENSED_SNAPSHOT.csv --timing YOUR_PRIVATE_TIMING.json --archive YOUR_FROZEN_SUMMARY_FOLDER
```

The matching private snapshot SHA-256 is `6d14f9b278472669891d6c9e20d8076ed00407a44d6f552919477d86108f077b` (18,201,198 bytes). The timing extract fingerprint is in config.json. Original vendor prices and per-forecast/outcome rows are deliberately excluded. Exact reproduction requires legitimate access to those matching inputs; this is not a self-contained public reforecast experiment.

Snapshot schema used: symbol, model, lookback, target_date (YYYY-MM-DD), phase (history/forward), variant (seed_42/seed_123/seed_2026), previous_close, actual_open/high/low/close, predicted_open/high/low/close. Saved bias, gross_usd, cost_usd, net_usd and always_long_net_usd/always_short_net_usd are independently recomputed and compared. Additional unused snapshot fields may remain. Actual candles must be finite and internally consistent; raw predicted candles stay unmodified, including invalid geometry. Unique key: variant/symbol/model/lookback/target_date.

Timing JSON: one object per scored forward forecast, keyed by those same five fields; created_at_utc and target_open_utc are timezone-aware ISO timestamps. Require all 264 rows to join uniquely and creation strictly before the stated open. Timing proves saved ordering, not live execution or target-input independence. Reference folder for verification: frozen history_by_seed.csv, settings.csv, uncertainty.csv and checks.json; PROJECT_CLOSED.json sits two directories above that folder. No reference private paths are built into the scripts.

## Samples and definitions

Historical comparison: July 2, 2025–October 16, 2026; 43,098 rows, 44 market/model/input settings and 132 seed-setting series. ES/NQ have 327 target dates each; GC/CL 326. Eleven settings per market: mini128/256/512/1024/2048; small128/256/512; base128/256/512. Three seeds reuse the same dates. Exclude 132 October19 historical-extension rows. Prospective: only October20–21, 264 rows across 132 series. The separate unfinished session-path study is not evaluated.

Direction = sign(predicted close - previous actual close). +1 long, -1 short, zero no position. Gross USD = round(direction * (actual close - actual open) * contract multiplier, 2). Cost if entered = 5 USD + 2*tick size*multiplier; otherwise zero. Net USD = round(gross - cost, 2). Archived assumptions: ES tick .25/multiplier50/cost30; NQ .25/20/15; GC .1/100/25; CL .01/1000/25. Constant-direction baselines use the same daily prices and per-trade costs. These are simulation marks and assumptions, not current broker quotes or guaranteed fills.

Mean absolute close error = mean(abs(predicted close - actual close)); baseline substitutes previous close. Error reduction = 100*(1 - model error/baseline error). Negative means worse. Direction accuracy uses correct signs divided by nonflat actual close-to-close dates; flat predictions on nonflat dates are wrong. Flat actual dates remain in trading calculations. The table seed average means three alternative totals averaged, not an executable ensemble or account return.

Invalid predicted candle = high below any predicted open/low/close, or low above any predicted open/high/close. Count once per forecast. All remain in price-error and trade calculations. Same-date seed unanimity = groups with three identical directions / all market-setting-date groups. Seeds/settings share outcomes.

Five-best-day stress: remove each seed's own five largest net days, then average remaining totals. It is hindsight, not a deployable rule. Double cost deducts a second identical cost from each entered trade. Closed-trade drawdown uses cumulative daily net with initial zero, highest prior peak minus later value; no intraday stress or margin is represented.

Circular resampling: average seeds by date, subtract same-date long or short baseline, draw consecutive 5- or 20-session blocks with replacement and wrap at sample end, truncate to original length, repeat 10,000 times. RNG20261021, order fixed in config and scripts. Report 2.5th/97.5th percentiles. These descriptive intervals do not adjust for selection or provide a probability of future profit.

## Findings and limitations

All132 historical series have worse close error than unchanged close;8109/43098 predicted candles are internally inconsistent;8647/14366 matched groups are unanimous. Full44-setting grid,132 historical series,132 forward series,44 agreement rows and12 interval rows are retained. Selected trading profits are not a dependable general edge: baselines, seeds, rare days, costs and uncertainty matter. Only two prospective dates were scored.

Checks independently recalculate all43,494 row arithmetic,132 historical/132 forward series, market-quality and agreement counts; compare132series/44settings/12intervals with the frozen report; verify264 timing joins; retain6 checked archive hashes; check3 invented mechanics. No model calls are replayed. Original continuous-futures data, contract/session conventions, model pretraining overlap and actual executable prices are not certified. Research inference reproduction needs the original frozen model/input manifests; those private projects and vendor inputs are not redistributed here.

Official model-family reference: https://github.com/shiyu-coder/Kronos (checked November5,2026). It supports the model description, not our performance findings. The original report's continuation suggestions were superseded by owner closure; no new experiment is authorized by this article.

Files: README.md, config.json, requirements.txt, reproduce.py, verify.py, results.json, settings.csv, seeds.csv, forward.csv, agreement.csv, uncertainty.csv, verification.json.
