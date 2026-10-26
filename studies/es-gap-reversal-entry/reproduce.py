"""Exploratory reversal entries; exact rules, shared sample and no holdout claim."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
import gap_base as base
import rules

RULES=['vwap','vwap5','cisd','both']
SCOPES=['all_session','overnight']

def prepare(g):
    g=g.reset_index(drop=True).copy()
    assert len(g)==1380 and g.timestamp_utc.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all()
    assert np.isfinite(g.volume).all() and g.volume.ge(0).all() and g.volume.cumsum().gt(0).all()
    g['et']=g.timestamp_utc.dt.tz_convert('America/New_York')
    g['vwap']=(((g.high+g.low+g.close)/3)*g.volume).cumsum()/g.volume.cumsum()
    g['session_high']=g.high.cummax();g['session_low']=g.low.cummin()
    return g,rules.five_minute_bars(g)

def run(raw,events,legacy=False):
    groups={day:g for day,g in raw.groupby('session_date')};trades=[]
    original=rules.simulate
    if legacy:rules.simulate=rules.simulate_legacy
    try:
        for e in events:
            g,bars=prepare(groups[e['date']]);opening=float(g.iloc[0].open);target=opening-e['initial_gap']
            event=pd.Series({'gap':e['initial_gap'],'entry18':opening,'target17':target,'weekday':pd.Timestamp(e['date']).day_name()},name=e['date'])
            for scope in SCOPES:
                for rule in RULES:
                    trade=rules.find_trade(g,bars,event,rule,scope)
                    if trade is not None:trades.append(trade)
    finally:rules.simulate=original
    return trades

def stats(values):return base.stats(values)

def describe(trades,events):
    n=len(trades);den=len(events);x=[t['pnl_net'] for t in trades];y=[t['pnl_stop_net'] for t in trades]
    assert n>1
    fixed=[e['hold_to_1700']-1 for e in events]
    return {'trades':n,'eligible_measurable_gaps':den,'signal_pct':100*n/den,
            'overnight_entries':sum(t['entry_idx']<930 for t in trades),'daytime_entries':sum(t['entry_idx']>=930 for t in trades),
            'target_exits':sum(t['outcome']=='target' for t in trades),'net_no_stop':stats(x),'net_with_stop':stats(y),
            'cost_scenarios_no_stop':{str(c):stats([t['pnl_gross']-c for t in trades]) for c in [.5,1.,2.,4.]},
            'without_largest_no_stop_winner_mean':(sum(x)-max(x))/(n-1),
            'without_largest_stop_winner_mean':(sum(y)-max(y))/(n-1),
            'stop_outcomes':{k:sum(t['stop_outcome']==k for t in trades) for k in ['target','stop','time']},
            'unresolved_same_minute_stop_target':sum(t['ambiguous_stop_target_bar'] for t in trades),
            'mean_per_eligible_gap_no_trade_zero':sum(x)/den,'fixed_1830_mean_per_same_eligible_gap':sum(fixed)/den,
            'paired_mean_difference':(sum(x)-sum(fixed))/den,
            'periods':{label:{'trades':len(chosen),'net_no_stop':stats([t['pnl_net'] for t in chosen]),'net_with_stop':stats([t['pnl_stop_net'] for t in chosen])}
                       for label,chosen in [('first_year',[t for t in trades if t['session_date']<'2025-08-29']),('second_year',[t for t in trades if t['session_date']>='2025-08-29'])]}}

def calculate(source):
    raw=base.load(source);signals,old,checks=base.extract(raw);events=[r for r in signals if r['full_day_quality']]
    trades=run(raw,events);legacy=run(raw,old,True)
    data={scope+'_'+rule:describe([t for t in trades if t['scope']==scope and t['rule']==rule],events) for scope in SCOPES for rule in RULES}
    return trades,legacy,events,checks,data

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',default=Path('output'),type=Path);a=p.parse_args()
    before=base.fingerprint(a.input);trades,legacy,events,checks,data=calculate(a.input)
    result={'question':'Can waiting for a reversal improve ES gap entries?', 'source_sha256':before,'checks':checks,
            'measurable_full_day_gaps':len(events),'first_morning_date':events[0]['date'],'last_morning_date':events[-1]['date'],
            'results':data,'legacy':{'eligible_gaps':122,'trade_records':len(legacy)},
            'selection_status':{'held_out_dates_tested':False,'reason':'The original exploration already used the entire available minute archive. Chronological halves reuse explored dates; no rule is selected or promoted as validated.'},
            'limitations':['131 reconstructed signals; 11 lack usable full-day outcomes. Later quality is not a real-time signal filter.',
                           'Overnight scope limits entry time only; every position may remain open until 17:00.',
                           'VWAP is approximated from candle high/low/close and volume, not transaction prices.',
                           'Eight overlapping comparisons on previously explored dates; largest-winner removal is sensitivity, not independent evidence.',
                           'Targets and entries are idealized; unresolved same-minute stop/target ties use stop first after known opening-price checks.']}
    assert base.fingerprint(a.input)==before;a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    pd.DataFrame([{'rule_and_entry_window':k,'trades':v['trades'],'eligible_gaps':v['eligible_measurable_gaps'],'mean_net_no_stop':v['net_no_stop']['mean'],'mean_net_with_stop':v['net_with_stop']['mean'],'mean_without_best_no_stop':v['without_largest_no_stop_winner_mean'],'no_trade_zero_mean_per_gap':v['mean_per_eligible_gap_no_trade_zero']} for k,v in data.items()]).to_csv(a.output/'rule_summary.csv',index=False)
    print(json.dumps({'measurable_gaps':len(events),'results':[{k:r[k] for k in ['trades','net_no_stop','net_with_stop','without_largest_no_stop_winner_mean']} for r in data.values()]},indent=2))

if __name__=='__main__':main()
