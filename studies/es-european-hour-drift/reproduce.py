"""Measure ES 02:00-to-03:00 America/New_York open-to-open movement.

Read-only licensed input. Only aggregate results are written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

SEED=20261015
DRAWS=10000


def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def observations(source):
    cols=['timestamp_utc','session_date','open','underlying_contract',
          'data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1:raise ValueError('Expected exactly one CSV in ZIP.')
        raw=pd.read_csv(z.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    if raw.timestamp_utc.duplicated().any() or not raw.timestamp_utc.is_monotonic_increasing:
        raise ValueError('Timestamps must be strictly ordered and unique.')
    if not raw.is_complete.eq(True).all():raise ValueError('Incomplete source bars require an explicit policy.')
    if not np.isfinite(raw.open).all() or not raw.open.gt(0).all():raise ValueError('Invalid opening price.')
    local=raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['date']=local.dt.strftime('%Y-%m-%d');raw['clock']=local.dt.strftime('%H:%M')
    raw['minute']=local.dt.hour*60+local.dt.minute
    raw['session_date']=raw.session_date.astype(str)
    selected=raw.loc[raw.clock.isin(['02:00','03:00','18:00','09:30'])]
    if selected.duplicated(['session_date','clock']).any():raise ValueError('Duplicate source-session boundary.')
    cuts={clock:g.set_index('session_date') for clock,g in selected.groupby('clock')}
    empty=raw.iloc[:0].set_index('session_date')
    entries=cuts.get('02:00',empty);exits=cuts.get('03:00',empty)
    interval_rows=raw.loc[raw.minute.between(120,180)].copy()
    interval_rows['bad']=interval_rows.data_condition.eq('degraded') | interval_rows.roll_transition.astype(str).str.lower().eq('true')
    bad=interval_rows.groupby('session_date').bad.any()
    count=raw.loc[raw.minute.between(120,179)].groupby('session_date').size()
    contracts=interval_rows.groupby('session_date').underlying_contract.nunique()
    records=[]
    excluded={k:[] for k in ['missing_03','contract_mismatch','wrong_elapsed_time']}
    for day,a in entries.iterrows():
        if day not in exits.index:excluded['missing_03'].append(day);continue
        b=exits.loc[day]
        if a.underlying_contract!=b.underlying_contract:
            excluded['contract_mismatch'].append(day);continue
        if b.timestamp_utc-a.timestamp_utc!=pd.Timedelta(minutes=60):
            excluded['wrong_elapsed_time'].append(day);continue
        if not a['date']==b['date']==day:raise ValueError('Source session label differs from actual hour date.')
        if a.timestamp_utc.tz_convert('America/New_York').weekday()>4:raise ValueError('Unexpected weekend hour.')
        match=False;full_points=None;full_bps=None
        if day in cuts.get('18:00',empty).index and day in cuts.get('09:30',empty).index:
            evening=cuts['18:00'].loc[day];morning=cuts['09:30'].loc[day]
            match=(evening.underlying_contract==morning.underlying_contract==a.underlying_contract and
                   morning.timestamp_utc-evening.timestamp_utc==pd.Timedelta(minutes=930) and
                   evening.timestamp_utc<a.timestamp_utc<b.timestamp_utc<morning.timestamp_utc)
            if match:
                full_points=morning.open-evening.open;full_bps=full_points/evening.open*10000
        records.append({'date':day,'entry':a.open,'points':b.open-a.open,
                        'bps':(b.open-a.open)/a.open*10000,'shared_overnight':bool(match),
                        'overnight_points':full_points,'overnight_bps':full_bps,
                        'observed_hour_minutes':int(count.get(day,0)),
                        'hour_flagged':bool(bad.get(day,True)),
                        'hour_contract_count':int(contracts.get(day,0)),
                        'strict':count.get(day,0)==60 and not bad.get(day,True) and contracts.get(day,0)==1,
                        'utc_entry_hour':int(a.timestamp_utc.hour)})
    frame=pd.DataFrame(records)
    checks={'source_rows':len(raw),'source_session_dates':raw.session_date.nunique(),
            '02_entry_candidates':len(entries),'03_without_02_dates':sorted(set(exits.index)-set(entries.index)),
            'excluded':excluded,'eligible_hours':len(frame),
            'first_date':frame.date.min() if len(frame) else None,'last_date':frame.date.max() if len(frame) else None,
            'strict_hours':int(frame.strict.sum()) if len(frame) else 0,
            'shared_overnight_hours':int(frame.shared_overnight.sum()) if len(frame) else 0,
            'source_dates_without_02_entry':sorted(set(raw.session_date)-set(entries.index)),
            'valid_hour_without_full_overnight_dates':frame.loc[~frame.shared_overnight,'date'].tolist() if len(frame) else [],
            'strict_excluded_dates':frame.loc[~frame.strict,['date','observed_hour_minutes','hour_flagged','hour_contract_count']].to_dict('records') if len(frame) else [],
            'utc_entry_hour_counts':{str(k):int(v) for k,v in frame.utc_entry_hour.value_counts().sort_index().items()} if len(frame) else {}}
    return frame,checks


def stats(values):
    x=np.asarray(values,dtype=float)
    if not len(x):return {'hours':0}
    return {'hours':len(x),'mean':float(x.mean()),'median':float(np.median(x)),
            'positive_hours':int((x>0).sum()),'flat_hours':int((x==0).sum()),
            'positive_pct':float((x>0).mean()*100),'minimum':float(x.min()),'maximum':float(x.max())}


def mean_ranges(frame):
    iso=pd.to_datetime(frame.date).dt.isocalendar()
    work=frame[['points','bps']].assign(week=iso.year.astype(str)+'-'+iso.week.astype(str))
    grouped=work.groupby('week')[['points','bps']].agg(['sum','count'])
    picks=np.random.default_rng(SEED).integers(0,len(grouped),size=(DRAWS,len(grouped)))
    return {unit+'_mean_95':np.quantile(grouped[(unit,'sum')].to_numpy()[picks].sum(axis=1)/
                                      grouped[(unit,'count')].to_numpy()[picks].sum(axis=1),[.025,.975]).tolist()
            for unit in ['points','bps']}


def summarize(frame):
    return {'points':stats(frame.points),'bps':stats(frame.bps),'uncertainty':mean_ranges(frame)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--output',type=Path,default=Path('output'))
    args=p.parse_args()
    before=fingerprint(args.input)
    frame,checks=observations(args.input)
    shared=frame.loc[frame.shared_overnight]
    result={'question':'Did ES rise on average from the 02:00 minute open to the 03:00 minute open in New York?',
            'source_sha256':before,'checks':checks,'main':summarize(frame),
            'strict_hour_quality':summarize(frame.loc[frame.strict]),
            'annual':{str(y):summarize(g) for y,g in frame.groupby(frame.date.str[:4])},
            'chronological_halves':{label:summarize(frame.loc[mask]) for label,mask in
                [('first_year',frame.date<'2025-08-29'),('second_year',frame.date>='2025-08-29')]},
            'costs_points':{str(cost):{'net':stats(frame.points-cost),
                                     'net_points_mean_95':[x-cost for x in mean_ranges(frame)['points_mean_95']]}
                            for cost in [.5,1.,2.,4.]},
            'shared_dates_comparison':{'one_hour':summarize(shared),
                                       'full_overnight_points':stats(shared.overnight_points),
                                       'full_overnight_bps':stats(shared.overnight_bps),
                                       'remaining_overnight_points':stats(shared.overnight_points-shared.points)},
            'resampling':{'unit':'Monday–Sunday calendar week of actual hour date','draws':DRAWS,'seed':SEED,
                          'method':'Resample complete observed weeks with replacement; means weight observations equally; 2.5th and 97.5th percentiles.',
                          'selection_adjustment':False},
            'limitations':['Fixed New York clock hour, not a constant European local opening time.',
                           'Same archive and previously explored time slice, not an independent or unseen test.',
                           'Source-quality checks are retrospective, not entry signals.',
                           'Recorded opens do not establish executable fills or actual costs.',
                           'No external paper is being replicated or cited as confirmation.']}
    if fingerprint(args.input)!=before:raise AssertionError('Source file changed.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    rows=[{'hour_date_year':year,'eligible_hours':x['points']['hours'],'mean_points':x['points']['mean'],
           'mean_bps':x['bps']['mean'],'positive_hours':x['points']['positive_hours'],
           'flat_hours':x['points']['flat_hours']} for year,x in result['annual'].items()]
    pd.DataFrame(rows).to_csv(args.output/'annual_summary.csv',index=False)
    print(json.dumps({k:result[k] for k in ['checks','main','strict_hour_quality','annual','chronological_halves','shared_dates_comparison']},indent=2))


if __name__=='__main__':main()
