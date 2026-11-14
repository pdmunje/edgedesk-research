# Do ES month and weekday patterns stay consistent over time?

Prepared November 5, 2026. Descriptive daily ES reconstruction pending owner review.

## Question, answer and boundaries

March had the highest earlier mean one-session close-to-close change: +0.099758% over 481 starting windows. Later it averaged -0.063472% over 154 and ranked tenth of twelve months. Monday stayed the highest-mean starting weekday, +0.078594% earlier and +0.128902% later. The full calendar grid is retained; neither a selected failure nor a selected winner establishes a live trading rule. Both periods were previously examined, not untouched validation.

Old source conversations asked about S&P cash-index and ES intraday seasonality. The original cash calculations and thirty-minute source were not recovered. This is a new explicit daily ES adaptation, not a claim to reproduce those old results or hourly patterns.

## Inputs

Privately supplied daily CSV with ISO time date labels and positive valid open, high, low, close fields; volume/extra fields unused. Ordered unique weekday dates and OHLC are checked. SHA-256 mismatch stops reproduction:

aa50dad895c5698ae35e24333cf093b682736a4d8477e53563ca7607ef7037eb

7,285 rows from 1997-09-09 to 2026-06-30. Original vendor rows remain private. Date-only labels do not establish exact cash/open/close availability. Gaps up to six calendar days, unknown full missing-session calendar, rolls/back adjustment/revisions and four nonquarter-price rows are retained and disclosed. No missing dates or prices are inserted. Prior matching of 1,504 supplied weekly OHLC groups is internal consistency, not feed/tradability certification.

## Exact anchored formulas and grouping

For starting close row t and h later stored sessions:

    points = close[t+h] - close[t]
    percent = 100 * (close[t+h] / close[t] - 1)
    mean = sum(percent) / eligible windows
    median = middle sorted percent; average middle two for even count

Group by MONTH or WEEKDAY OF t, the starting close label. Ending prices may cross months; a group is not a calendar-month return. Monday means Monday close to a later close, not Monday intraday. Horizons1/2/3/5/21 count supplied rows, not elapsed days or guaranteed calendar weeks/months. Each starting row with h future rows is eligible.

Invented examples: closes100→105 give5 points and5%; closes200→210 give10 points but still5%. These are teaching values, not actual ES observations.

All sample: all eligible horizons. Earlier: ending date before2020-01-01, thus start also earlier. Later: starting date>=2020-01-01. Windows crossing2020 remain in All but not either phase. For horizons1/2/3/5/21, full counts are7,284/7,283/7,282/7,280/7,264; split-crossing counts1/2/3/5/21. Tail rows without future horizon are excluded, not filled with invented outcomes.

## Entry timing and cost sensitivity

Close marks are descriptive; a rule evaluated after that close cannot automatically enter at the same mark. Keep the same ending close but use next stored open:

    next_open_gross_percent = 100*(close[t+h]-open[t+1])/open[t+1]
    next_open_cost1_percent = 100*(close[t+h]-open[t+1]-1)/open[t+1]

One point is an illustrative total round-trip cost, not a current broker quote, verified slippage or actual execution. Invented close100, next open103, end105 gives gross close-mark5%, next-open1.941748% and cost1 sensitivity0.970874%. No tick rounding, spread, liquidity, latency or native session-time fill is established.

All percentages divide by the relevant price reference, not equity, margin or initial risk. No account sizing, compounded equity, annual return, drawdown or maximum loss is modeled. Multi-session windows overlap and are not an executable portfolio allocation. Larger cumulative changes at longer horizons do not by themselves establish stronger seasonality.

## Full search and retrospective ranking diagnostic

Retain twelve months, five weekdays and five horizons in each of All/Earlier/Later. That is85 nonbaseline cells per period,255 in total, plus15 baselines =270 summary rows. Save counts, positive/zero/negative outcomes, means, medians, point changes, origin-date range and both timing/cost sensitivities. Cells, horizons, periods and baselines reuse prices and are not independent studies/trials.

For a transparent diagnostic, pick the earlier highest mean ONE-session month and separately weekday, ties by smaller numeric key. Inspect that same key later and rank among all later keys. This is retrospective selection, not an original frozen trading rule. Monthly mean signs agree in8/12 cells and weekday signs in4/5; these are displayed-group counts, not confidence probabilities. The later all-starting-date one-session mean is0.059475%, compared with0.029290% earlier; each baseline includes its subgroups.

Means can depend on crisis years and large moves. Show median alongside later means but do not claim robust future probabilities. The later period runs only January2020–June2026. No independent-trial interval, significance test or untouched date validation is supplied.

## Reproduce

Python 3.12.14 standard library only; no network/dependency installation needed:

    python -B reproduce.py YOUR_AUTHORIZED_DAILY.csv
    python -B verify.py YOUR_AUTHORIZED_DAILY.csv

reproduce.py writes results.json and all-calendar-cells.csv. verify.py independently assembles Decimal returns and calendar buckets, checks all 36,393 forward windows and 270 summary denominators/signs/mean units/timing/cost sensitivities, 30 month/weekday partition checks, five split-coverage checks and three invented arithmetic checks. verification.json records actual results. Native/cash session and live execution behavior are not checked.

This study shares the daily input with weekly-candle and dip-limit articles; they are not independent confirmation. It differs from a Sunday-night-only overnight return. Public-intended files contain only this method, configuration, original portable calculation/checking programs and summaries. No vendor rows, original charts, raw chats, private website/card code, machine paths or credentials are included.

Change history: November 5, 2026 — explicit daily reconstruction, full search retained, matched private article/card prepared. Specific-version human approval remains pending.
