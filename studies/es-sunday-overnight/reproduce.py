"""Compare actual Sunday-evening ES entries with other weekday overnights.

Read-only licensed inputs; only aggregate outputs, never raw price bars.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

SEED = 20261015
DRAWS = 10000


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def minute_nights(source):
    cols = ['timestamp_utc','session_date','open','underlying_contract',
            'data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as archive:
        names = [x for x in archive.namelist() if x.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Expected exactly one CSV in ZIP.')
        raw = pd.read_csv(archive.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    if raw.timestamp_utc.duplicated().any() or not raw.timestamp_utc.is_monotonic_increasing:
        raise ValueError('Minute timestamps must be strictly ordered and unique.')
    if not raw.is_complete.eq(True).all():
        raise ValueError('Incomplete bars require a separately documented policy.')
    if not np.isfinite(raw.open).all() or not raw.open.gt(0).all():
        raise ValueError('Opening prices must be finite and positive.')
    raw['session_date'] = raw.session_date.astype(str)
    local = raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['clock'] = local.dt.strftime('%H:%M')
    raw['local_date'] = local.dt.strftime('%Y-%m-%d')
    raw['minute'] = local.dt.hour*60+local.dt.minute
    cuts = raw.loc[raw.clock.isin(['18:00','09:30'])]
    if cuts.duplicated(['session_date','clock']).any():
        raise ValueError('Duplicate overnight boundary.')
    entry = cuts.loc[cuts.clock.eq('18:00')].set_index('session_date')
    exit_rows = cuts.loc[cuts.clock.eq('09:30')].set_index('session_date')
    paired = entry[['timestamp_utc','open','underlying_contract']].join(
        exit_rows[['timestamp_utc','open','underlying_contract']],lsuffix='_entry',rsuffix='_exit')
    missing = paired.timestamp_utc_exit.isna()
    mismatch = paired.underlying_contract_entry.ne(paired.underlying_contract_exit) & ~missing
    duration = paired.timestamp_utc_exit.sub(paired.timestamp_utc_entry).dt.total_seconds().eq(930*60)
    valid = ~missing & ~mismatch & duration
    nights = paired.loc[valid].copy()
    entry_local = nights.timestamp_utc_entry.dt.tz_convert('America/New_York')
    exit_local = nights.timestamp_utc_exit.dt.tz_convert('America/New_York')
    if not np.array_equal(exit_local.dt.strftime('%Y-%m-%d'),nights.index):
        raise ValueError('Source session date disagrees with actual morning date.')
    nights['entry_date'] = entry_local.dt.strftime('%Y-%m-%d')
    nights['sunday'] = entry_local.dt.dayofweek.eq(6)
    if not exit_local.loc[nights.sunday].dt.dayofweek.eq(0).all():
        raise ValueError('Sunday entry does not exit Monday morning.')
    if not entry_local.loc[~nights.sunday].dt.dayofweek.isin([0,1,2,3]).all():
        raise ValueError('Unexpected non-Sunday entry weekday.')
    nights['points'] = nights.open_exit - nights.open_entry
    nights['bps'] = nights.points / nights.open_entry * 10000
    degraded = raw.data_condition.eq('degraded').groupby(raw.session_date).any()
    roll = raw.roll_transition.astype(str).str.lower().eq('true').groupby(raw.session_date).any()
    overnight_counts = raw.loc[(raw.minute>=1080)|(raw.minute<570)].groupby('session_date').size()
    nights['strict'] = ~degraded.reindex(nights.index) & ~roll.reindex(nights.index) & overnight_counts.reindex(nights.index).eq(930)
    return nights, {'source_rows':len(raw), 'source_session_dates':raw.session_date.nunique(),
                    'entry_candidates':len(entry), 'missing_exit_dates':paired.index[missing].tolist(),
                    'contract_mismatch_dates':paired.index[mismatch].tolist(),
                    'wrong_elapsed_time_dates':paired.index[~missing & ~duration].tolist(),
                    'eligible_nights':len(nights), 'strict_nights':int(nights.strict.sum()),
                    'first_session':str(nights.index.min()),'last_session':str(nights.index.max()),
                    'actual_sunday_monday_labels_verified':True}


def stats(values):
    values=np.asarray(values,dtype=float)
    return {'nights':len(values),'mean':float(np.mean(values)), 'median':float(np.median(values)),
            'positive_nights':int((values>0).sum()), 'flat_nights':int((values==0).sum()),
            'positive_pct':float((values>0).mean()*100),'minimum':float(values.min()),'maximum':float(values.max())}


def interval(frame):
    iso=pd.to_datetime(frame.index).isocalendar()
    week=np.asarray(iso.year.astype(str)+'-'+iso.week.astype(str))
    data=pd.DataFrame({'week':week,'sunday':np.where(frame.sunday,frame.bps,np.nan),
                       'other':np.where(~frame.sunday,frame.bps,np.nan)})
    grouped=data.groupby('week').agg({'sunday':['sum','count'],'other':['sum','count']})
    rng=np.random.default_rng(SEED)
    picks=rng.integers(0,len(grouped),size=(DRAWS,len(grouped)))
    means={}
    for side in ['sunday','other']:
        means[side]=grouped[(side,'sum')].to_numpy()[picks].sum(axis=1)/grouped[(side,'count')].to_numpy()[picks].sum(axis=1)
    return {'sunday_mean_bps_95':np.quantile(means['sunday'],[.025,.975]).tolist(),
            'other_mean_bps_95':np.quantile(means['other'],[.025,.975]).tolist(),
            'difference_sunday_minus_other_bps_95':np.quantile(means['sunday']-means['other'],[.025,.975]).tolist(),
            'difference_bps':float(frame.loc[frame.sunday,'bps'].mean()-frame.loc[~frame.sunday,'bps'].mean())}


def comparison(frame):
    answer={side:{'points':stats(frame.loc[mask,'points']),'bps':stats(frame.loc[mask,'bps'])}
            for side,mask in [('sunday',frame.sunday),('other',~frame.sunday)]}
    answer['uncertainty']=interval(frame)
    return answer


def history_nights(source):
    raw=pd.read_csv(source,usecols=['time','open','close'])
    times=pd.to_datetime(raw.time,utc=True)
    if times.duplicated().any() or not times.is_monotonic_increasing:
        raise ValueError('Historical timestamps must be strictly ordered and unique.')
    if not np.isfinite(raw[['open','close']].to_numpy()).all() or not raw.open.gt(0).all():
        raise ValueError('Historical prices must be finite and opening prices positive.')
    local=times.dt.tz_convert('America/New_York')
    candidates=local.dt.strftime('%H:%M').eq('18:00')
    valid=candidates & local.shift(-1).dt.strftime('%H:%M').eq('09:30') & times.shift(-1).sub(times).eq(pd.Timedelta(minutes=930))
    dates=local.shift(-1).dt.strftime('%Y-%m-%d')
    frame=pd.DataFrame({'session_date':dates,'points':raw.close-raw.open,
                        'bps':(raw.close-raw.open)/raw.open*10000,
                        'sunday':local.dt.dayofweek.eq(6),'entry_date':local.dt.strftime('%Y-%m-%d')}).loc[valid].set_index('session_date')
    days=local.loc[valid].dt.dayofweek
    if not days.isin([0,1,2,3,6]).all() or frame.index.duplicated().any():
        raise ValueError('Unexpected historical entry weekday or duplicate morning date.')
    return frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--history-input',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('output'))
    args=parser.parse_args()
    before={name:fingerprint(source) for name,source in [('minute',args.input),('history',args.history_input)]}
    nights,checks=minute_nights(args.input)
    costs={}
    for cost in [.5,1.,2.,4.]:
        work=nights.assign(net_points=nights.points-cost,net_bps=(nights.points-cost)/nights.open_entry*10000)
        costs[str(cost)]={side:{'net_points':stats(work.loc[mask,'net_points']),
                              'net_bps':stats(work.loc[mask,'net_bps'])}
                         for side,mask in [('sunday',work.sunday),('other',~work.sunday)]}
    history=history_nights(args.history_input)
    groups=[('2000–2010','2000-01-01','2010-12-31'),('2011–2020','2011-01-01','2020-12-31'),
            ('2021–2023','2021-01-01','2023-12-31'),('2024–Oct 5 2026','2024-01-01','2026-10-05')]
    historical={name:comparison(history.loc[history.index.to_series().between(start,end)]) for name,start,end in groups}
    selected=nights.loc[nights.sunday]
    trimmed=selected.loc[selected.bps.abs().sort_values(kind='stable').index[:-5]]
    overlap=history.loc[history.index.isin(nights.index)]
    hashes_after={name:fingerprint(source) for name,source in [('minute',args.input),('history',args.history_input)]}
    if before != hashes_after:
        raise AssertionError('A source file changed during calculation.')
    result={'question':'Did actual Sunday-evening ES entries differ from other weekday overnights?',
            'source_sha256':before,'checks':checks,'main':comparison(nights),
            'stricter':comparison(nights.loc[nights.strict]),'costs_points_per_night':costs,
            'minute_by_year':{str(y):comparison(g) for y,g in nights.groupby(nights.index.str[:4])},
            'all_entry_weekdays':{str(day):{'points':stats(g.points),'bps':stats(g.bps)}
                                  for day,g in nights.groupby(pd.to_datetime(nights.entry_date).dt.day_name())},
            'historical_periods':historical,'historical_overlap_same_515_dates':comparison(overlap),
            'remove_five_largest_absolute_sunday_moves':{'removed_nights':5,'bps':stats(trimmed.bps),'points':stats(trimmed.points)},
            'resampling':{'unit':'Monday–Sunday calendar week of actual morning date', 'draws':DRAWS,'seed':SEED,
                          'method':'Resample whole weeks with replacement; use the same drawn weeks for both groups; compute each group mean and their difference.',
                          'selection_adjustment':False},
            'limitations':['Previously explored weekday split, not a fresh holdout.',
                           'Other nights are pooled and their unequal counts weight the average.',
                           'Sunday and weekday price references do not model executable reopen fills.',
                           'Continuous historical contract selection and adjustment rules remain unverified.',
                           'Recent historical and minute observations overlap, not independent evidence.']}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    annual=[]
    for year,data in result['minute_by_year'].items():
        for side in ['sunday','other']:
            x=data[side]
            annual.append({'morning_year':year,'entry_group':side,'nights':x['bps']['nights'],
                           'mean_points':x['points']['mean'],'mean_bps':x['bps']['mean'],
                           'median_bps':x['bps']['median'],'positive_pct':x['bps']['positive_pct']})
    pd.DataFrame(annual).to_csv(args.output/'annual_summary.csv',index=False)
    print(json.dumps({'checks':checks,'main':result['main'],'stricter':result['stricter'],'history':historical},indent=2))


if __name__=='__main__':
    main()
