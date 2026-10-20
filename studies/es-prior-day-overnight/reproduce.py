"""Does an ES daytime decline precede a stronger overnight move?

Read a licensed minute archive without modifying it. Write aggregate results only.
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
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def observations(source):
    cols = ['timestamp_utc','session_date','open','underlying_contract',
            'data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as archive:
        names = [x for x in archive.namelist() if x.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Expected exactly one CSV inside ZIP.')
        raw = pd.read_csv(archive.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    if raw.timestamp_utc.duplicated().any() or not raw.timestamp_utc.is_monotonic_increasing:
        raise ValueError('Timestamps must be ordered and unique.')
    if not raw.is_complete.eq(True).all():
        raise ValueError('Incomplete source bars need an explicit policy.')
    if not np.isfinite(raw.open).all() or not raw.open.gt(0).all():
        raise ValueError('Prices must be finite and positive.')
    local = raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['day'] = local.dt.strftime('%Y-%m-%d')
    raw['clock'] = local.dt.strftime('%H:%M')
    raw['minute'] = local.dt.hour*60 + local.dt.minute
    raw['session_date'] = raw.session_date.astype(str)
    cuts = raw.loc[raw.clock.isin(['09:30','16:00','18:00'])]
    if cuts.duplicated(['day','clock']).any():
        raise ValueError('Duplicate boundary on an actual calendar day.')
    daytime = cuts.loc[cuts.clock.isin(['09:30','16:00'])].set_index(['day','clock'])
    exits = cuts.loc[cuts.clock.eq('09:30')].set_index('session_date')
    entries = cuts.loc[cuts.clock.eq('18:00')].set_index('session_date')
    day_counts = raw.loc[raw.minute.between(570,959)].groupby('day').size()
    day_bad = raw.loc[raw.minute.between(570,960)].assign(
        bad=lambda x: x.data_condition.eq('degraded') | x.roll_transition.astype(str).str.lower().eq('true')
    ).groupby('day').bad.any()
    night_counts = raw.loc[(raw.minute>=1080)|(raw.minute<570)].groupby('session_date').size()
    session_bad = raw.assign(bad=raw.data_condition.eq('degraded') | raw.roll_transition.astype(str).str.lower().eq('true')).groupby('session_date').bad.any()
    excluded = {key:[] for key in ['missing_exit','wrong_overnight_elapsed','overnight_contract',
                                 'missing_required_daytime','different_daytime_contract','wrong_daytime_elapsed']}
    records = []
    paired_nights = 0
    for morning, entry in entries.iterrows():
        if morning not in exits.index:
            excluded['missing_exit'].append(morning);continue
        end = exits.loc[morning]
        if end.timestamp_utc-entry.timestamp_utc != pd.Timedelta(minutes=930):
            excluded['wrong_overnight_elapsed'].append(morning);continue
        if end.underlying_contract != entry.underlying_contract:
            excluded['overnight_contract'].append(morning);continue
        start_local = entry.timestamp_utc.tz_convert('America/New_York')
        end_local = end.timestamp_utc.tz_convert('America/New_York')
        if end_local.strftime('%Y-%m-%d') != morning or start_local.weekday() not in [0,1,2,3,6]:
            raise ValueError('Unexpected actual entry date or morning label.')
        paired_nights += 1
        sunday = start_local.weekday()==6
        # Sunday uses exactly Friday; a missing holiday boundary is never filled
        # with Thursday or another older daytime session.
        prior_day = (start_local.normalize()-pd.DateOffset(days=2 if sunday else 0)).strftime('%Y-%m-%d')
        if (prior_day,'09:30') not in daytime.index or (prior_day,'16:00') not in daytime.index:
            excluded['missing_required_daytime'].append({'morning':morning,'required_day':prior_day});continue
        a = daytime.loc[(prior_day,'09:30')];b = daytime.loc[(prior_day,'16:00')]
        if not a.underlying_contract == b.underlying_contract == entry.underlying_contract:
            excluded['different_daytime_contract'].append(morning);continue
        if b.timestamp_utc-a.timestamp_utc != pd.Timedelta(minutes=390):
            excluded['wrong_daytime_elapsed'].append(morning);continue
        if not b.timestamp_utc < entry.timestamp_utc:
            raise ValueError('Daytime signal was not known before evening entry.')
        records.append({'date':morning,'prior_day':prior_day,'entry_weekday':start_local.day_name(),
                        'sunday':sunday,'negative':b.open<a.open,'flat_day':b.open==a.open,
                        'prior_points':b.open-a.open,'entry':entry.open,
                        'points':end.open-entry.open,'bps':(end.open-entry.open)/entry.open*10000,
                        'strict':night_counts.get(morning,0)==930 and not session_bad.get(morning,True)
                                 and day_counts.get(prior_day,0)==390 and not day_bad.get(prior_day,True)})
    frame = pd.DataFrame(records)
    checks = {'source_rows':len(raw),'evening_candidates':len(entries),'paired_nights':paired_nights,
              'eligible_with_required_daytime':len(frame),'exclusions':excluded,
              'flat_daytime_observations':int(frame.flat_day.sum()) if len(frame) else 0,
              'four_prices_same_contract':True,'daytime_known_before_entry':True,
              'first_morning':frame.date.min() if len(frame) else None,
              'last_morning':frame.date.max() if len(frame) else None}
    return frame,checks


def stats(values):
    x = np.asarray(values,dtype=float)
    if not len(x):return {'nights':0}
    return {'nights':len(x),'mean':float(x.mean()),'median':float(np.median(x)),
            'positive_nights':int((x>0).sum()),'flat_nights':int((x==0).sum()),
            'positive_pct':float((x>0).mean()*100),'minimum':float(x.min()),'maximum':float(x.max())}


def interval(frame):
    iso = pd.to_datetime(frame.date).dt.isocalendar()
    week = iso.year.astype(str)+'-'+iso.week.astype(str)
    sums = pd.DataFrame({'week':week,'down':np.where(frame.negative,frame.bps,np.nan),
                         'other':np.where(~frame.negative,frame.bps,np.nan)}).groupby('week').agg(['sum','count'])
    rng = np.random.default_rng(SEED)
    picks = rng.integers(0,len(sums),size=(DRAWS,len(sums)))
    means = {}
    for side in ['down','other']:
        means[side] = sums[(side,'sum')].to_numpy()[picks].sum(axis=1)/sums[(side,'count')].to_numpy()[picks].sum(axis=1)
    return {'down_mean_bps_95':np.quantile(means['down'],[.025,.975]).tolist(),
            'other_mean_bps_95':np.quantile(means['other'],[.025,.975]).tolist(),
            'difference_down_minus_other_bps_95':np.quantile(means['down']-means['other'],[.025,.975]).tolist(),
            'difference_bps':float(frame.loc[frame.negative,'bps'].mean()-frame.loc[~frame.negative,'bps'].mean())}


def comparison(frame):
    return {**{side:{'points':stats(frame.loc[mask,'points']),'bps':stats(frame.loc[mask,'bps'])}
               for side,mask in [('down',frame.negative),('other',~frame.negative)]},
            'uncertainty':interval(frame)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('output'))
    args = p.parse_args()
    before = fingerprint(args.input)
    nights,checks = observations(args.input)
    annual = {str(y):comparison(g) for y,g in nights.groupby(nights.date.str[:4])}
    costs = {str(cost):{side:stats(nights.loc[mask,'points']-cost)
                       for side,mask in [('down',nights.negative),('other',~nights.negative)]}
             for cost in [.5,1.,2.,4.]}
    result = {'question':'Did a negative 09:30-to-16:00 daytime move precede stronger 18:00-to-09:30 ES movement?',
              'source_sha256':before,'checks':checks,'main':comparison(nights),
              'other_weekday_entries':comparison(nights.loc[~nights.sunday]),
              'sunday_entries':comparison(nights.loc[nights.sunday]),
              'stricter':comparison(nights.loc[nights.strict]),
              'chronological_halves':{label:comparison(nights.loc[mask]) for label,mask in
                  [('first_year',nights.date<'2025-08-29'),('second_year',nights.date>='2025-08-29')]},
              'annual':annual,'costs_points':costs,
              'unfiltered_eligible':{'points':stats(nights.points),'bps':stats(nights.bps)},
              'resampling':{'unit':'Monday–Sunday calendar week of morning date','draws':DRAWS,'seed':SEED,
                            'method':'Draw weeks with replacement, same draws for both groups, percentiles 2.5 and 97.5.',
                            'selection_adjustment':False},
              'limitations':['Sign comparison previously explored; not a new holdout or a causal claim.',
                             'Sunday uses Friday daytime, other nights use same-calendar-day daytime.',
                             'Strict quality flags include later data and are retrospective diagnostics.',
                             'No measured fills, spreads, broker fees, stops or intranight risk.',
                             'Older candle source does not supply an equivalent 16:00 boundary.']}
    if fingerprint(args.input) != before:raise AssertionError('Source file changed during calculation.')
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    rows = [{'morning_year':year,'daytime_group':side,'nights':x[side]['points']['nights'],
             'mean_points':x[side]['points']['mean'],'mean_bps':x[side]['bps']['mean'],
             'positive_nights':x[side]['bps']['positive_nights']} for year,x in annual.items() for side in ['down','other']]
    pd.DataFrame(rows).to_csv(args.output/'annual_summary.csv',index=False)
    print(json.dumps({'checks':checks,'main':result['main'],'other_weekday_entries':result['other_weekday_entries'],
                      'sunday_entries':result['sunday_entries'],'stricter':result['stricter'],
                      'halves':result['chronological_halves']},indent=2))


if __name__=='__main__':main()
