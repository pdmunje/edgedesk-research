"""Recalculate ES reopen-gap touches and an idealized target/time-exit fade.

Read-only licensed minute archive. Export aggregate results, never vendor bars.
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


def trade(path,entry,target,direction,time_exit):
    touches=path.high.ge(target) if direction==1 else path.low.le(target)
    touched=bool(touches.any())
    first=int(np.flatnonzero(touches.to_numpy())[0]) if touched else None
    gross=min(direction*(target-entry),direction*((target if touched else time_exit)-entry))
    return touched,first,float(gross)


def observations(source):
    cols=['timestamp_utc','session_date','open','high','low','close','underlying_contract',
          'data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1:raise ValueError('Expected exactly one CSV in archive.')
        raw=pd.read_csv(z.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    if raw.timestamp_utc.duplicated().any() or not raw.timestamp_utc.is_monotonic_increasing:
        raise ValueError('Timestamps must be ordered and unique.')
    prices=raw[['open','high','low','close']]
    if not np.isfinite(prices.to_numpy()).all() or not prices.gt(0).all().all():raise ValueError('Invalid prices.')
    if not (raw.high.ge(raw[['open','close','low']].max(axis=1)) & raw.low.le(raw[['open','close','high']].min(axis=1))).all():
        raise ValueError('Inconsistent candle ranges.')
    if not raw.is_complete.eq(True).all():raise ValueError('Incomplete supplied bars need an explicit policy.')
    local=raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['date']=local.dt.strftime('%Y-%m-%d');raw['clock']=local.dt.strftime('%H:%M')
    raw['minute']=local.dt.hour*60+local.dt.minute;raw['session_date']=raw.session_date.astype(str)
    raw['bad']=raw.data_condition.eq('degraded') | raw.roll_transition.astype(str).str.lower().eq('true')
    cuts=raw.loc[raw.clock.isin(['16:59','18:00','09:30'])]
    if cuts.duplicated(['date','clock']).any():raise ValueError('Duplicate calendar boundary.')
    closes=cuts.loc[cuts.clock.eq('16:59')].set_index('date')
    entries=cuts.loc[cuts.clock.eq('18:00')]
    groups={str(day):g for day,g in raw.groupby('session_date',sort=True)}
    previous={day:prev for prev,day in zip(groups,list(groups)[1:])}
    excluded={key:[] for key in ['missing_target','target_contract_change','missing_0930',
                                 'wrong_time_or_exit_contract']}
    rows=[];quality_failures=[]
    for a in entries.itertuples():
        start=a.timestamp_utc.tz_convert('America/New_York')
        if start.weekday() not in [0,1,2,3,6]:raise ValueError('Unexpected evening weekday.')
        target_date=(start.normalize()-pd.DateOffset(days=2 if start.weekday()==6 else 0)).strftime('%Y-%m-%d')
        if target_date not in closes.index:excluded['missing_target'].append(a.session_date);continue
        target_bar=closes.loc[target_date]
        if target_bar.underlying_contract!=a.underlying_contract:
            excluded['target_contract_change'].append(a.session_date);continue
        target=float(target_bar.close);entry=float(a.open)
        if not target_bar.timestamp_utc+pd.Timedelta(minutes=1)<=a.timestamp_utc:
            raise ValueError('Target close was not known before the reopen.')
        g=groups[a.session_date]
        end_rows=g.loc[g.clock.eq('09:30')]
        if len(end_rows)!=1:excluded['missing_0930'].append(a.session_date);continue
        end=end_rows.iloc[0]
        if end.timestamp_utc-a.timestamp_utc!=pd.Timedelta(minutes=930) or end.underlying_contract!=a.underlying_contract:
            excluded['wrong_time_or_exit_contract'].append(a.session_date);continue
        if end['date']!=a.session_date:raise ValueError('Source date differs from actual morning date.')
        on=g.loc[(g.timestamp_utc>=a.timestamp_utc)&(g.timestamp_utc<end.timestamp_utc)]
        all_same=on.underlying_contract.eq(a.underlying_contract).all()
        window_quality=(len(on)==930 and all_same and not bool(on.bad.any()) and not bool(target_bar.bad) and not bool(end.bad))
        if not window_quality:
            quality_failures.append({'date':a.session_date,'overnight_minutes':len(on),'one_overnight_contract':bool(all_same),
                                     'overnight_flagged':bool(on.bad.any()),'target_bar_flagged':bool(target_bar.bad),'exit_bar_flagged':bool(end.bad)})
        prior=groups.get(previous.get(a.session_date,''),raw.iloc[:0])
        legacy_quality=(len(on)==930 and len(g.loc[g.minute.between(570,1019)])==450 and all_same and
                        not g.data_condition.eq('degraded').any() and not prior.data_condition.eq('degraded').any())
        gap=entry-target
        if gap==0:
            rows.append({'date':a.session_date,'gap':0.,'window_quality':bool(window_quality),
                         'legacy_quality':bool(legacy_quality),'zero':True});continue
        direction=-1 if gap>0 else 1
        touched,first,gross=trade(on,entry,target,direction,float(end.open))
        minute0=touched and first==0
        delay_gross=None;delay_touch=None
        later=on.loc[on.timestamp_utc>=a.timestamp_utc+pd.Timedelta(minutes=1)]
        if not minute0 and len(later) and later.iloc[0].timestamp_utc==a.timestamp_utc+pd.Timedelta(minutes=1):
            delayed_entry=float(later.iloc[0].open)
            if direction*(target-delayed_entry)>0:
                delay_touch,_,delay_gross=trade(later,delayed_entry,target,direction,float(end.open))
        rows.append({'date':a.session_date,'gap':gap,'zero':False,'window_quality':bool(window_quality),
                     'legacy_quality':bool(legacy_quality),'touch':touched,'entry_minute_touch':minute0,
                     'capped_time_exit':not touched and direction*(float(end.open)-entry)>abs(gap),
                     'gross_points':gross,'target_points':abs(gap),'delayed_gross':delay_gross,'delayed_touch':delay_touch})
    frame=pd.DataFrame(rows,columns=['date','gap','zero','window_quality','legacy_quality','touch',
                                    'entry_minute_touch','capped_time_exit','gross_points','target_points','delayed_gross','delayed_touch'])
    for flag in ['zero','window_quality','legacy_quality']:frame[flag]=frame[flag].astype(bool)
    checks={'source_rows':len(raw),'source_session_dates':len(groups),'evening_candidates':len(entries),
            'sequential_exclusions':excluded,'paired_with_target_and_exit':len(frame),
            'window_quality_sessions_including_zero':int(frame.window_quality.sum()),
            'zero_gaps_in_window_quality':int((frame.window_quality & frame.zero).sum()),
            'window_quality_failures_including_zero':quality_failures,
            'nonzero_gaps_before_quality':int((~frame.zero).sum()),
            'nonzero_excluded_by_window_quality':frame.loc[~frame.zero & ~frame.window_quality,'date'].tolist(),
            'exact_target_calendar_dates_used':True,
            'first_event':frame.loc[frame.window_quality & ~frame.zero,'date'].min() if len(frame.loc[frame.window_quality & ~frame.zero]) else None,
            'last_event':frame.loc[frame.window_quality & ~frame.zero,'date'].max() if len(frame.loc[frame.window_quality & ~frame.zero]) else None}
    return frame,checks


def stats(values):
    x=np.asarray(values,dtype=float)
    if not len(x):return {'events':0}
    return {'events':len(x),'mean':float(x.mean()),'median':float(np.median(x)),'sum':float(x.sum()),
            'positive_events':int((x>0).sum()),'flat_events':int((x==0).sum()),
            'positive_pct':float((x>0).mean()*100),'minimum':float(x.min()),'maximum':float(x.max())}


def mean_range(frame):
    iso=pd.to_datetime(frame.date).dt.isocalendar()
    work=frame[['gross_points']].assign(week=iso.year.astype(str)+'-'+iso.week.astype(str))
    g=work.groupby('week').gross_points.agg(['sum','count'])
    picks=np.random.default_rng(SEED).integers(0,len(g),size=(DRAWS,len(g)))
    means=g['sum'].to_numpy()[picks].sum(axis=1)/g['count'].to_numpy()[picks].sum(axis=1)
    return np.quantile(means,[.025,.975]).tolist()


def summarize(frame):
    return {'events':len(frame),'touch_events':int(frame.touch.sum()),'touch_pct':float(frame.touch.mean()*100),
            'entry_minute_touches':int(frame.entry_minute_touch.sum()),
            'capped_time_exit_cases':int(frame.capped_time_exit.sum()),
            'gross_points':stats(frame.gross_points),'gross_mean_points_95':mean_range(frame),
            'touch_group':stats(frame.loc[frame.touch,'gross_points']),
            'no_touch_group':stats(frame.loc[~frame.touch,'gross_points']),
            'delayed_one_minute':{'gross_points':stats(frame.delayed_gross.dropna()),
                                  'net_one_point':stats(frame.delayed_gross.dropna()-1),
                                  'skipped_events':int(frame.delayed_gross.isna().sum())}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',type=Path,default=Path('output'))
    args=p.parse_args();before=fingerprint(args.input)
    frame,checks=observations(args.input)
    main_frame=frame.loc[frame.window_quality & ~frame.zero].copy()
    main_frame['touch']=main_frame.touch.astype(bool);main_frame['entry_minute_touch']=main_frame.entry_minute_touch.astype(bool)
    legacy=frame.loc[frame.legacy_quality & ~frame.zero].copy()
    legacy['touch']=legacy.touch.astype(bool);legacy['entry_minute_touch']=legacy.entry_minute_touch.astype(bool)
    main_result=summarize(main_frame)
    result={'question':'Do frequent ES reopen-gap touches imply profitable target/time-exit fades?',
            'source_sha256':before,'checks':checks,'main':main_result,'full_day_quality_check':summarize(legacy),
            'costs_points':{str(cost):{'net':stats(main_frame.gross_points-cost),
                                     'net_mean_points_95':[x-cost for x in main_result['gross_mean_points_95']]}
                            for cost in [.5,1.,2.,4.]},
            'annual':{str(y):summarize(g) for y,g in main_frame.groupby(main_frame.date.str[:4])},
            'chronological_halves':{label:summarize(main_frame.loc[mask]) for label,mask in
                                   [('first_year',main_frame.date<'2025-08-29'),('second_year',main_frame.date>='2025-08-29')]},
            'resampling':{'unit':'Monday–Sunday calendar week of actual morning date','draws':DRAWS,'seed':SEED,
                          'selection_adjustment':False},
            'limitations':['Idealized reopen-open execution, target-touch execution and minute sequencing are unverified.',
                           'Coverage/quality checks use later information and are retrospective sample diagnostics.',
                           'No stop, margin, actual fills, slippage, intranight risk or compounded account modeled.',
                           'Delayed entry changes the rule and event sample; it is not an independent confirmation.',
                           'Same previously explored minute archive as related overnight and gap studies.']}
    if fingerprint(args.input)!=before:raise AssertionError('Source file changed.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    annual=[{'morning_year':year,'events':x['events'],'target_touch_events':x['touch_events'],
             'target_touch_pct':x['touch_pct'],'mean_gross_points':x['gross_points']['mean'],
             'mean_net_one_point':x['gross_points']['mean']-1} for year,x in result['annual'].items()]
    pd.DataFrame(annual).to_csv(args.output/'annual_summary.csv',index=False)
    print(json.dumps({k:result[k] for k in ['checks','main','full_day_quality_check','annual']},indent=2))


if __name__=='__main__':main()
