"""Explore gap-size thresholds with explicit frequency and touch denominators."""
import argparse
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import gap_base

POINTS=[.25,.5,1,2,3,5,8,10,15,20,30,50]
SCALED=[0,.01,.02,.03,.05,.075,.1,.15,.2,.25,.3,.4,.5,1.]
EXPECTED={'T01':120,'T02':240,'T03':120,'T04':60,'T05':180,'T06':150,'T07':60,
          'T08':60,'T09':90,'T10':120,'T11':90,'T12':30,'T13':60}


def scales(daily):
    """Observed source-session TR; first-fragment exclusion; Wilder smoothing."""
    output={};true_ranges=[];clean=[];previous=None;atr=None
    for day,row in daily.sort_index().iterrows():
        if row.fragment:
            previous=None;continue
        own=float(row.high-row.low)
        tr=own
        if previous is not None and previous['close'] is not None and pd.notna(row.contract) and previous['contract']==row.contract:
            tr=max(own,abs(float(row.high)-previous['close']),abs(float(row.low)-previous['close']))
        true_ranges.append(tr);clean.append(bool(row.clean))
        if len(true_ranges)==14:atr=sum(true_ranges)/14
        elif len(true_ranges)>14:atr=(13*atr+tr)/14
        output[day]={'prior_range':own,'atr14':atr,'last14_clean':len(clean)>=14 and all(clean[-14:]),
                     'end':row.end}
        previous={'close':None if pd.isna(row['close']) else float(row['close']),
                  'contract':row.get('close_contract',row.contract)}
    return output


def minute_sample(source):
    frame,base_checks=gap_base.observations(source)
    with zipfile.ZipFile(source) as z:
        raw=pd.read_csv(z.open([n for n in z.namelist() if n.lower().endswith('.csv')][0]),
                        usecols=['timestamp_utc','session_date','open','high','low','close','underlying_contract','data_condition','roll_transition'],
                        parse_dates=['timestamp_utc'],low_memory=False)
    local=raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['clock']=local.dt.strftime('%H:%M');raw['session_date']=raw.session_date.astype(str)
    daily=[]
    for i,(day,g) in enumerate(raw.groupby('session_date',sort=True)):
        a=g.loc[g.clock.eq('18:00')];b=g.loc[g.clock.eq('16:59')]
        contract=str(g.underlying_contract.iloc[0]) if g.underlying_contract.nunique()==1 else None
        clean=(len(g)==1380 and g.underlying_contract.nunique()==1 and not g.data_condition.eq('degraded').any() and
               not g.roll_transition.astype(str).str.lower().eq('true').any())
        daily.append({'date':day,'high':g.high.max(),'low':g.low.min(),'close':b.close.iloc[0] if len(b) else None,
                      'contract':contract,'close_contract':str(b.underlying_contract.iloc[0]) if len(b) else None,
                      'fragment':i==0 and not len(a),'clean':clean,'end':g.timestamp_utc.max()})
    features=scales(pd.DataFrame(daily).set_index('date'))
    entries=raw.loc[raw.clock.eq('18:00')].set_index('session_date')
    selected=frame.loc[frame.window_quality].copy()
    selected['abs_gap']=selected.gap.abs()
    for idx,r in selected.iterrows():
        entry=entries.loc[r.date].timestamp_utc
        start=entry.tz_convert('America/New_York')
        required=(start.normalize()-pd.DateOffset(days=2 if start.weekday()==6 else 0)).strftime('%Y-%m-%d')
        feature=features.get(required,{})
        if feature and not feature['end']<entry:raise ValueError('Feature uses future information.')
        selected.loc[idx,'prior_range']=feature.get('prior_range',np.nan)
        selected.loc[idx,'atr14']=feature.get('atr14',np.nan)
        selected.loc[idx,'last14_clean']=feature.get('last14_clean',False)
    selected['gap_range']=selected.abs_gap/selected.prior_range.replace(0,np.nan)
    selected['gap_atr']=selected.abs_gap/selected.atr14.replace(0,np.nan)
    selected['touch']=selected.touch.fillna(False).astype(bool)
    return selected,{'base':base_checks,'initial_fragment_excluded_from_volatility':True,
                    'range_available_sessions':int(selected.gap_range.notna().sum()),
                    'atr_available_sessions':int(selected.gap_atr.notna().sum()),
                    'last14_complete_unflagged_sessions':int(selected.last14_clean.sum())}


def history_sample(source):
    raw=pd.read_csv(source)
    if raw.duplicated(['trade_date','slot_id']).any():raise ValueError('Duplicate historical slot.')
    for key in ['time','end_time']:raw[key]=pd.to_datetime(raw[key],utc=True)
    if not np.isfinite(raw[['open','high','low','close']].to_numpy()).all():raise ValueError('Invalid historical prices.')
    if not raw.eligible.isin([True,False]).all():raise ValueError('Unexpected eligibility flag.')
    raw['trade_date']=raw.trade_date.astype(str)
    groups={day:g.set_index('slot_id').sort_index() for day,g in raw.groupby('trade_date',sort=True)}
    daily=[];closes={}
    for day,g in groups.items():
        a=g.loc['T01'] if 'T01' in g.index else None;b=g.loc['T13'] if 'T13' in g.index else None
        if b is not None:
            end=b.end_time.tz_convert('America/New_York')
            if end.strftime('%H:%M')=='17:00':closes[end.strftime('%Y-%m-%d')]=(day,b)
        complete=(set(g.index)==set(EXPECTED) and g.eligible.all() and g.observed_minutes.sum()>=.95*1380)
        known=lambda r: None if pd.isna(r['source']) or pd.isna(r.roll_segments) else str(r['source'])+'|'+str(r.roll_segments)
        labels=g.apply(known,axis=1)
        daily.append({'date':day,'high':g.high.max(),'low':g.low.min(),'close':b.close if b is not None else None,
                      'contract':labels.iloc[0] if labels.notna().all() and labels.nunique()==1 else None,
                      'close_contract':known(b) if b is not None else None,
                      'fragment':a is None,'clean':bool(complete),'end':g.end_time.max()})
    features=scales(pd.DataFrame(daily).set_index('date'))
    excluded={k:0 for k in ['slots_or_coverage','missing_exact_target','target_source_or_segment','bad_boundaries']}
    rows=[]
    for day,g in groups.items():
        if set(g.index)!=set(EXPECTED) or not g.eligible.all():excluded['slots_or_coverage']+=1;continue
        on=g.loc[[f'T{i:02}' for i in range(1,8)]];rth=g.loc[[f'T{i:02}' for i in range(8,14)]]
        if on.observed_minutes.sum()<.95*930 or rth.observed_minutes.sum()<.95*450:
            excluded['slots_or_coverage']+=1;continue
        a=on.iloc[0];end=rth.iloc[0];local=a.time.tz_convert('America/New_York')
        actual_end=end.time.tz_convert('America/New_York')
        durations=(g.end_time-g.time).dt.total_seconds().to_numpy()
        contiguous=all(g.iloc[i].end_time==g.iloc[i+1].time for i in range(len(g)-1))
        if local.strftime('%H:%M')!='18:00' or actual_end.strftime('%H:%M')!='09:30' or actual_end.strftime('%Y-%m-%d')!=day or end.time-a.time!=pd.Timedelta(minutes=930) or not np.array_equal(durations,np.array([EXPECTED[k]*60 for k in g.index])) or not contiguous:
            excluded['bad_boundaries']+=1;continue
        if local.weekday() not in [0,1,2,3,6]:raise ValueError('Unexpected historical entry weekday.')
        required=(local.normalize()-pd.DateOffset(days=2 if local.weekday()==6 else 0)).strftime('%Y-%m-%d')
        if required not in closes:excluded['missing_exact_target']+=1;continue
        prior_day,b=closes[required]
        same_segment=lambda v: str(v)==str(a.roll_segments)
        if not bool(b.eligible) or b['source']!=a['source'] or not same_segment(b.roll_segments) or not on['source'].eq(a['source']).all() or not on.roll_segments.map(same_segment).all() or end['source']!=a['source'] or not same_segment(end.roll_segments):
            excluded['target_source_or_segment']+=1;continue
        feature=features.get(prior_day,{})
        if feature and not feature['end']<=a.time:raise ValueError('Historical feature uses future records.')
        gap=float(a.open-b.close);direction=-1 if gap>0 else 1
        touch=bool((on.low.le(b.close) if direction==-1 else on.high.ge(b.close)).any()) if gap else False
        gross=min(abs(gap),direction*((float(b.close) if touch else float(end.open))-float(a.open))) if gap else np.nan
        prior_range=feature.get('prior_range');atr=feature.get('atr14')
        rows.append({'date':day,'gap':gap,'abs_gap':abs(gap),'zero':gap==0,'touch':touch,'gross_points':gross,
                     'prior_range':prior_range,'atr14':atr,'last14_clean':feature.get('last14_clean',False),
                     'gap_range':abs(gap)/prior_range if prior_range else np.nan,'gap_atr':abs(gap)/atr if atr else np.nan})
    return pd.DataFrame(rows),{'source_rows':len(raw),'source_dates':len(groups),'sequential_exclusions':excluded,
                               'eligible_sessions_including_zero':len(rows),
                               'first_morning':min(r['date'] for r in rows),'last_morning':max(r['date'] for r in rows),
                               'coverage_rule':'At least 95% observed minutes separately in overnight and daytime; all 13 slots eligible.'}


def threshold(frame,column,level):
    eligible=frame.loc[frame[column].notna()].copy()
    selected=eligible.loc[~eligible.zero & eligible[column].ge(level)].copy()
    n=len(selected);base=len(eligible)
    return {'threshold':level,'eligible_sessions_including_zero':base,'selected_nonzero_events':n,
            'frequency_pct':100*n/base if base else None,'touch_events':int(selected.touch.sum()),
            'touch_pct':100*float(selected.touch.sum())/n if n else None,
            'gross_points':gap_base.stats(selected.gross_points),
            'net_one_point':gap_base.stats(selected.gross_points-1),
            'net_mean_points_95':[v-1 for v in gap_base.mean_range(selected)] if n else None}


def tables(frame):
    return {name:[threshold(frame,col,v) for v in values] for name,col,values in
            [('points','abs_gap',POINTS),('prior_range_fraction','gap_range',SCALED),('atr14_fraction','gap_atr',SCALED)]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--history-input',required=True,type=Path)
    p.add_argument('--output',type=Path,default=Path('output'));args=p.parse_args()
    before={k:gap_base.fingerprint(v) for k,v in [('minute',args.input),('history',args.history_input)]}
    minute,mc=minute_sample(args.input);history,hc=history_sample(args.history_input)
    a=minute.set_index('date');b=history.set_index('date');shared=sorted(set(a.index)&set(b.index))
    nz=[d for d in shared if not a.loc[d,'zero'] and not b.loc[d,'zero']]
    overlap={'shared_sessions_including_zero':len(shared),'shared_nonzero_events':len(nz),
             'gap_disagreement_events':sum(abs(float(a.loc[d,'gap'])-float(b.loc[d,'gap']))>1e-9 for d in nz),
             'touch_disagreement_events':sum(bool(a.loc[d,'touch'])!=bool(b.loc[d,'touch']) for d in nz),
             'max_gross_points_difference':max(abs(float(a.loc[d,'gross_points'])-float(b.loc[d,'gross_points'])) for d in nz),
             'note':'Shared dates are source comparisons, not extra independent observations.'}
    result={'question':'Does increasing an ES reopen-gap size threshold improve target/time-exit results?',
            'source_sha256':before,'minute_checks':mc,'history_checks':hc,'overlap':overlap,
            'minute':tables(minute),'history':tables(history),
            'minute_last14_complete_unflagged':tables(minute.loc[minute.last14_clean.eq(True)]),
            'period_checks_two_point_threshold':{label:threshold(frame.loc[frame.date.between(start,end)],'abs_gap',2.)
                for label,frame,start,end in [('minute_earlier_year',minute,'2024-08-29','2025-08-28'),
                    ('minute_later_year',minute,'2025-08-29','2026-08-28'),
                    ('history_2017_2020',history,'2017-01-01','2020-12-31'),
                    ('history_2021_2023',history,'2021-01-01','2023-12-31'),
                    ('history_2024_oct2026',history,'2024-01-01','2026-10-06')]},
            'resampling':{'draws':gap_base.DRAWS,'seed':gap_base.SEED,'unit':'Monday–Sunday calendar week of actual morning date','selection_adjustment':False},
            'limitations':['Threshold grid previously explored; no threshold selected on an untouched holdout.',
                           'Observed session ranges can be understated by missing minutes or short source sessions.',
                           'Wilder ATR uses earlier observed source sessions, not future/current-session ranges.',
                           'Historical slot input permits missing minutes and has source/roll segments, not independently verified dated-contract history.',
                           'All fills, same-minute timing and one-point cost remain assumptions.']}
    if before!={k:gap_base.fingerprint(v) for k,v in [('minute',args.input),('history',args.history_input)]}:raise AssertionError('Source changed.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    rows=[{'source':source,'measure':metric,'threshold':r['threshold'],'eligible_sessions':r['eligible_sessions_including_zero'],
           'selected_events':r['selected_nonzero_events'],'frequency_pct':r['frequency_pct'],'touch_events':r['touch_events'],
           'touch_pct':r['touch_pct'],'mean_net_one_point':r['net_one_point'].get('mean')}
          for source in ['minute','history'] for metric,group in result[source].items() for r in group]
    pd.DataFrame(rows).to_csv(args.output/'threshold_summary.csv',index=False)
    print(json.dumps({'minute_checks':mc,'history_checks':hc,'overlap':overlap,'minute_points':result['minute']['points'],'history_points':result['history']['points']},indent=2))


if __name__=='__main__':main()
