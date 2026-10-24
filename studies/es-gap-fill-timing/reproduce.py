"""Descriptive first-touch timing; no trading execution or profit assumed."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

CUTS=[1,2,5,10,15,30,60,120,240,360,600,930,1380]
BINS=[0,1,5,15,30,60,120,360,930,1380]

def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()

def first_touch(g,target,gap):
    hits=g.low.le(target) if gap>0 else g.high.ge(target)
    return int(np.flatnonzero(hits.to_numpy())[0]) if hits.any() else None

def summarize(rows):
    n=len(rows);times=[r['minute'] for r in rows];on=sum(t is not None and t<930 for t in times)
    return {'events':n,'overnight_touches':on,
        'cumulative':[{'before_minute':m,'touches':sum(t is not None and t<m for t in times),
            'pct_all_gaps':100*sum(t is not None and t<m for t in times)/n if n else None,
            'pct_overnight_touches':100*sum(t is not None and t<m for t in times)/on if on and m<=930 else None} for m in CUTS],
        'exclusive_buckets':[{'from_minute':a,'before_minute':b,'events':sum(t is not None and a<=t<b for t in times)} for a,b in zip(BINS[:-1],BINS[1:])],
        'no_touch_before_1700':sum(t is None for t in times),
        'conditional':[{'still_open_at_minute':m,'still_open':sum(t is None or t>=m for t in times),
            'later_overnight_touches':sum(t is not None and m<=t<930 for t in times),
            'pct_remaining':100*sum(t is not None and m<=t<930 for t in times)/sum(t is None or t>=m for t in times) if any(t is None or t>=m for t in times) else None}
            for m in [1,5,15,30,60,120,360]]}

def calculate(source):
    cols=['timestamp_utc','session_date','open','high','low','close','underlying_contract','data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        if len(names)!=1:raise ValueError('Expected one CSV.')
        raw=pd.read_csv(z.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    assert raw.timestamp_utc.is_monotonic_increasing and not raw.timestamp_utc.duplicated().any()
    assert raw.is_complete.eq(True).all()
    assert np.isfinite(raw[['open','high','low','close']].to_numpy()).all()
    assert raw[['open','high','low','close']].gt(0).all().all()
    assert (raw.low.le(raw[['open','close','high']].min(axis=1)) & raw.high.ge(raw[['open','close','low']].max(axis=1))).all()
    local=raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['date']=local.dt.strftime('%Y-%m-%d');raw['clock']=local.dt.hour*60+local.dt.minute
    raw['session_date']=raw.session_date.astype(str)
    raw['bad']=raw.data_condition.eq('degraded') | raw.roll_transition.astype(str).str.lower().eq('true')
    closes=raw.loc[raw.clock.eq(1019)].set_index('date');assert not closes.index.duplicated().any()
    groups={day:g for day,g in raw.groupby('session_date',sort=True)}
    previous={day:prev for prev,day in zip(groups,list(groups)[1:])}
    main=[];old=[];overnight=[];prior_degraded={}
    exclusions={k:0 for k in ['missing_required_close','target_contract_change','missing_or_misaligned_full_day','flagged_or_mixed_contract_full_day','zero_gap']}
    candidates=0
    for day,g in groups.items():
        entries=g.loc[g.clock.eq(1080)]
        if not len(entries):continue
        assert len(entries)==1;candidates+=1;a=entries.iloc[0]
        start=a.timestamp_utc;et=start.tz_convert('America/New_York')
        assert et.weekday() in [0,1,2,3,6]
        assert (et+pd.DateOffset(days=1)).strftime('%Y-%m-%d')==day
        path=g.loc[(g.timestamp_utc>=start)&(g.timestamp_utc<start+pd.Timedelta(minutes=1380))]
        on=path.loc[path.timestamp_utc<start+pd.Timedelta(minutes=930)]
        prior=groups.get(previous.get(day,''),raw.iloc[:0]);prior_closes=prior.loc[prior.clock.eq(1019)]
        # Reconstruct the old saved sample, including its previous-observed-session target.
        if len(prior_closes)==1:
            target_bar=prior_closes.iloc[0];gap=float(a.open-target_bar.close)
            if (gap!=0 and target_bar.underlying_contract==a.underlying_contract and len(on)==930 and len(path)==1380
                and on.underlying_contract.eq(a.underlying_contract).all()
                and not g.data_condition.eq('degraded').any() and not prior.data_condition.eq('degraded').any()):
                old.append({'date':day,'gap':gap,'minute':first_touch(path,float(target_bar.close),gap)})
        target_date=(et.normalize()-pd.DateOffset(days=2 if et.weekday()==6 else 0)).strftime('%Y-%m-%d')
        if target_date not in closes.index:exclusions['missing_required_close']+=1;continue
        target_bar=closes.loc[target_date]
        assert target_bar.timestamp_utc+pd.Timedelta(minutes=1)<=start
        if target_bar.underlying_contract!=a.underlying_contract:exclusions['target_contract_change']+=1;continue
        gap=float(a.open-target_bar.close)
        row={'date':day,'gap':gap,'minute':first_touch(path,float(target_bar.close),gap) if gap else None}
        # Same 400-event overnight comparator as the related gap studies, but no daytime inference.
        exit_rows=g.loc[g.timestamp_utc.eq(start+pd.Timedelta(minutes=930))]
        if (len(on)==930 and on.underlying_contract.eq(a.underlying_contract).all() and not on.bad.any()
            and not target_bar.bad and len(exit_rows)==1 and not exit_rows.iloc[0].bad
            and exit_rows.iloc[0].underlying_contract==a.underlying_contract and gap!=0):
            overnight.append(dict(row,minute=first_touch(on,float(target_bar.close),gap)))
        if len(path)!=1380 or not path.timestamp_utc.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all():
            exclusions['missing_or_misaligned_full_day']+=1;continue
        if target_bar.bad or path.bad.any() or not path.underlying_contract.eq(a.underlying_contract).all():
            exclusions['flagged_or_mixed_contract_full_day']+=1;continue
        if gap==0:exclusions['zero_gap']+=1;continue
        main.append(row);prior_degraded[day]=bool(prior.data_condition.eq('degraded').any())
    assert candidates==sum(exclusions.values())+len(main)
    return main,old,overnight,{'source_rows':len(raw),'source_session_dates':len(groups),'evening_candidates':candidates,
        'sequential_exclusions':exclusions,'first_morning_date':main[0]['date'] if main else None,'last_morning_date':main[-1]['date'] if main else None,
        'old_events_absent_from_main':sorted(set(r['date'] for r in old)-set(r['date'] for r in main)),
        'main_only_events_with_prior_session_degraded':sum(prior_degraded[d] for d in set(r['date'] for r in main)-set(r['date'] for r in old)),
        'old_inclusive_cutoff_counts':{str(m):sum(r['minute'] is not None and r['minute']<=m for r in old) for m in [5,60]}}

def main_cli():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',default=Path('output'),type=Path)
    a=p.parse_args();before=fingerprint(a.input);rows,old,on,checks=calculate(a.input)
    result={'question':'When do ES reopen gaps first touch the required prior close?', 'source_sha256':before,
        'checks':checks,'main':summarize(rows),'original_observed_target_sample':summarize(old),
        'overnight_only_comparator':{k:v for k,v in summarize(on).items() if k in ['events','overnight_touches','cumulative','conditional']},
        'groups':{name:summarize(chosen) for name,chosen in [
            ('sunday_reopen',[r for r in rows if pd.Timestamp(r['date']).weekday()==0]),
            ('other_weekday_reopens',[r for r in rows if pd.Timestamp(r['date']).weekday()!=0]),
            ('gap_under_one_point',[r for r in rows if abs(r['gap'])<1]),
            ('gap_one_to_under_three',[r for r in rows if 1<=abs(r['gap'])<3]),
            ('gap_three_to_under_ten',[r for r in rows if 3<=abs(r['gap'])<10]),
            ('gap_ten_or_more',[r for r in rows if abs(r['gap'])>=10]),
            ('first_year',[r for r in rows if r['date']<'2025-08-29']),
            ('second_year',[r for r in rows if r['date']>='2025-08-29'])]},
        'overlap':{'main_shared_with_400_overnight':len(set(r['date'] for r in rows)&set(r['date'] for r in on)),
                   'main_shared_with_original':len(set(r['date'] for r in rows)&set(r['date'] for r in old))},
        'timing':'Minute start offset; t < cutoff. First-minute touch lies in [18:00,18:01); no exact seconds or execution inferred.',
        'limitations':['Retrospective complete full-day selection uses later coverage and quality, not a live eligibility signal.',
                       'No trading P&L, fees, spread, slippage, queue or stop-order execution modeled.',
                       'Same previously explored minute archive; groups and periods are descriptive, not independent validation.',
                       'Coarser historical candles cannot establish minute-level first-touch timing.']}
    # Remove misleading daytime cutoff from the overnight-only comparator.
    result['overnight_only_comparator']['cumulative']=[r for r in result['overnight_only_comparator']['cumulative'] if r['before_minute']<=930]
    assert fingerprint(a.input)==before
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    pd.DataFrame(result['main']['cumulative']).to_csv(a.output/'cumulative.csv',index=False)
    print(json.dumps({k:result[k] for k in ['checks','main','overlap']},indent=2))

if __name__=='__main__':main_cli()
