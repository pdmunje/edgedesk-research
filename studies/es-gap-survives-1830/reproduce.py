"""ES gaps still open at 18:30: observable selection, later outcomes and costs."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

SEED=20261016

def fingerprint(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return h.hexdigest()

def load(source):
    cols=['timestamp_utc','session_date','open','high','low','close','underlying_contract','data_condition','is_complete','roll_transition']
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        raw=pd.read_csv(z.open(names[0]),usecols=cols,parse_dates=['timestamp_utc'])
    assert raw.timestamp_utc.is_monotonic_increasing and not raw.timestamp_utc.duplicated().any()
    assert raw.is_complete.eq(True).all()
    assert np.isfinite(raw[['open','high','low','close']].to_numpy()).all() and raw[['open','high','low','close']].gt(0).all().all()
    assert (raw.low.le(raw[['open','close','high']].min(axis=1)) & raw.high.ge(raw[['open','close','low']].max(axis=1))).all()
    local=raw.timestamp_utc.dt.tz_convert('America/New_York')
    raw['date']=local.dt.strftime('%Y-%m-%d');raw['clock']=local.dt.hour*60+local.dt.minute
    raw['session_date']=raw.session_date.astype(str)
    raw['bad']=raw.data_condition.eq('degraded') | raw.roll_transition.astype(str).str.lower().eq('true')
    return raw

def touch(path,target,direction):
    return path.high.ge(target) if direction==1 else path.low.le(target)

def simulate(path,entry,target,direction,exit_price,stop_distance=None,gap_aware=True):
    """Target capped; stop gaps use adverse open; unresolved intraminute ties stop first."""
    reward=direction*(target-entry);assert reward>0
    stop=entry-direction*stop_distance if stop_distance is not None else None
    ties=0
    for b in path.itertuples():
        hit_target=b.high>=target if direction==1 else b.low<=target
        hit_stop=(b.low<=stop if direction==1 else b.high>=stop) if stop is not None else False
        if stop is not None and gap_aware:
            if direction*(b.open-stop)<0:return float(direction*(b.open-entry)),'stop_gap',ties
            if direction*(b.open-target)>=0:return float(reward),'target',ties
        if hit_stop:
            ties+=int(hit_target)
            return float(-stop_distance),'stop',ties
        if hit_target:return float(reward),'target',ties
    return float(min(reward,direction*(exit_price-entry))),'time',ties

def extract(raw):
    groups={day:g for day,g in raw.groupby('session_date',sort=True)}
    previous={day:prev for prev,day in zip(groups,list(groups)[1:])}
    closes=raw.loc[raw.clock.eq(1019)].set_index('date');assert not closes.index.duplicated().any()
    signals=[];legacy=[]
    counts=dict.fromkeys(['missing_required_close','target_contract_change','opening_or_1830_boundary_unusable','zero_initial_gap','touched_before_1830','crossed_at_1830_open'],0)
    candidates=0
    def make(g,a,target_bar,day):
        start=a.timestamp_utc;t30=start+pd.Timedelta(minutes=30);morning=start+pd.Timedelta(minutes=930)
        opening=g.loc[(g.timestamp_utc>=start)&(g.timestamp_utc<t30)]
        entry30=g.loc[g.timestamp_utc.eq(t30)]
        if len(opening)!=30 or len(entry30)!=1:return None,'opening_or_1830_boundary_unusable'
        b=entry30.iloc[0]
        if target_bar.bad or opening.bad.any() or not opening.underlying_contract.eq(a.underlying_contract).all() or b.underlying_contract!=a.underlying_contract:
            return None,'opening_or_1830_boundary_unusable'
        target=float(target_bar.close);gap=float(a.open-target)
        if gap==0:return None,'zero_initial_gap'
        direction=-1 if gap>0 else 1
        if touch(opening,target,direction).any():return None,'touched_before_1830'
        entry=float(b.open);residual=direction*(target-entry)
        if residual<=0:return None,'crossed_at_1830_open'
        later=g.loc[(g.timestamp_utc>=t30)&(g.timestamp_utc<morning)]
        exitrows=g.loc[g.timestamp_utc.eq(morning)]
        on_quality=(len(later)==900 and later.underlying_contract.eq(a.underlying_contract).all() and not later.bad.any()
                    and len(exitrows)==1 and exitrows.iloc[0].underlying_contract==a.underlying_contract and not exitrows.iloc[0].bad)
        full=g.loc[(g.timestamp_utc>=t30)&(g.timestamp_utc<start+pd.Timedelta(minutes=1380))]
        full_quality=(len(full)==1350 and full.underlying_contract.eq(a.underlying_contract).all() and not full.bad.any())
        row={'date':day,'initial_gap':gap,'residual':float(residual),'movement':'toward' if residual<abs(gap) else 'away' if residual>abs(gap) else 'unchanged',
             'overnight_quality':bool(on_quality),'full_day_quality':bool(full_quality),'first_minute_touch':False}
        if on_quality:
            hit=touch(later,target,direction);first=int(np.flatnonzero(hit.to_numpy())[0]) if hit.any() else None
            row.update(touch=bool(hit.any()),first_touch=first,first_minute_touch=first==0)
            for name,distance in [('no_stop',None),('stop_1_distance',max(residual,1.)),('stop_2_distance',max(2*residual,1.))]:
                result,outcome,ties=simulate(later,entry,target,direction,float(exitrows.iloc[0].open),distance)
                row[name]=result;row[name+'_outcome']=outcome;row[name+'_ties']=ties
            # Illustrative one-minute delay: exclude touches before entry, then require target still ahead.
            row['delayed_one_minute']=None
            if first!=0:
                dpath=later.iloc[1:];de=float(dpath.iloc[0].open)
                if direction*(target-de)>0:row['delayed_one_minute']=simulate(dpath,de,target,direction,float(exitrows.iloc[0].open))[0]
        if full_quality:
            row['full_day_touch']=bool(touch(full,target,direction).any())
            row['hold_to_1700']=simulate(full,entry,target,direction,float(full.iloc[-1].close))[0]
        return row,None
    for day,g in groups.items():
        a_rows=g.loc[g.clock.eq(1080)]
        if not len(a_rows):continue
        assert len(a_rows)==1;candidates+=1;a=a_rows.iloc[0];et=a.timestamp_utc.tz_convert('America/New_York')
        assert et.weekday() in [0,1,2,3,6] and (et+pd.DateOffset(days=1)).strftime('%Y-%m-%d')==day
        prior=groups.get(previous.get(day,''),raw.iloc[:0]);priorclose=prior.loc[prior.clock.eq(1019)]
        # Reconstruct the older 122-event sample separately, without adopting its future-data selection.
        on=g.loc[(g.timestamp_utc>=a.timestamp_utc)&(g.timestamp_utc<a.timestamp_utc+pd.Timedelta(minutes=930))]
        full=g.loc[(g.timestamp_utc>=a.timestamp_utc)&(g.timestamp_utc<a.timestamp_utc+pd.Timedelta(minutes=1380))]
        if (len(priorclose)==1 and len(on)==930 and len(full)==1380 and not g.data_condition.eq('degraded').any()
            and not prior.data_condition.eq('degraded').any() and priorclose.iloc[0].underlying_contract==a.underlying_contract):
            target=float(priorclose.iloc[0].close);gap=float(a.open-target);direction=-1 if gap>0 else 1
            opening=on.iloc[:30];entry30=g.loc[g.timestamp_utc.eq(a.timestamp_utc+pd.Timedelta(minutes=30))]
            if gap and len(entry30)==1 and not touch(opening,target,direction).any():
                entry=float(entry30.iloc[0].open);residual=direction*(target-entry);assert residual>0
                later=on.iloc[30:];exit09=g.loc[g.clock.eq(570)].iloc[0];rth=full.iloc[930:]
                hit=touch(later,target,direction);all_hit=touch(full.iloc[30:],target,direction)
                first=int(np.flatnonzero(all_hit.to_numpy())[0]) if all_hit.any() else None
                old={'date':day,'initial_gap':gap,'residual':residual,'first_touch':first,'touch':bool(hit.any()),
                     'no_stop':float(direction*((target if hit.any() else exit09.open)-entry)),
                     'hold_to_1700':float(direction*((target if all_hit.any() else rth.iloc[-1].close)-entry))}
                for k,d in [('stop_1_distance',max(residual,1.)),('stop_2_distance',max(residual*2,1.))]:
                    old[k],old[k+'_outcome'],_=simulate(later,entry,target,direction,float(exit09.open),d,gap_aware=False)
                legacy.append(old)
        target_date=(et.normalize()-pd.DateOffset(days=2 if et.weekday()==6 else 0)).strftime('%Y-%m-%d')
        if target_date not in closes.index:counts['missing_required_close']+=1;continue
        target_bar=closes.loc[target_date];assert target_bar.timestamp_utc+pd.Timedelta(minutes=1)<=a.timestamp_utc
        if target_bar.underlying_contract!=a.underlying_contract:counts['target_contract_change']+=1;continue
        row,reason=make(g,a,target_bar,day)
        if reason:counts[reason]+=1
        else:signals.append(row)
    assert len(signals)+sum(counts.values())==candidates
    checks={'source_rows':len(raw),'source_session_dates':len(groups),'evening_candidates':candidates,'sequential_signal_exclusions':counts,
            'signals_at_1830':len(signals),'later_unusable_overnight':sum(not r['overnight_quality'] for r in signals),
            'later_unusable_full_day':sum(not r['full_day_quality'] for r in signals)}
    return signals,legacy,checks

def stats(values):
    x=np.asarray(values,dtype=float)
    if not len(x):return {'events':0}
    return {'events':len(x),'mean':float(x.mean()),'median':float(np.median(x)),'sum':float(x.sum()),
            'positive_events':int((x>0).sum()),'flat_events':int((x==0).sum()),'positive_pct':float((x>0).mean()*100),'minimum':float(x.min()),'maximum':float(x.max())}

def summary(rows):
    if not rows:return {'events':0}
    n=len(rows)
    return {'events':n,'touches':sum(r['touch'] for r in rows),'touch_pct':100*sum(r['touch'] for r in rows)/n,
            'first_minute_touches':sum(r['first_minute_touch'] for r in rows),
            'initial_gap_median':float(np.median([abs(r['initial_gap']) for r in rows])),
            'residual_gap_median':float(np.median([r['residual'] for r in rows])),
            'rules':{name:{'gross':stats([r[name] for r in rows]),'net_one_point':stats([r[name]-1 for r in rows]),
                           'outcomes':{out:sum(r[name+'_outcome']==out for r in rows) for out in ['target','stop','stop_gap','time']},
                           'ambiguous_minutes_stop_first':sum(r[name+'_ties'] for r in rows)} for name in ['no_stop','stop_1_distance','stop_2_distance']},
            'no_stop_touch_group':stats([r['no_stop'] for r in rows if r['touch']]),
            'no_stop_no_touch_group':stats([r['no_stop'] for r in rows if not r['touch']])}

def weekly_range(rows):
    work=pd.DataFrame([{'week':pd.Timestamp(r['date']).strftime('%G-%V'),'net':r['no_stop']-1} for r in rows])
    groups=work.groupby('week').net.agg(['sum','count']);rng=np.random.default_rng(SEED)
    picks=rng.integers(0,len(groups),size=(10000,len(groups)))
    means=groups['sum'].to_numpy()[picks].sum(axis=1)/groups['count'].to_numpy()[picks].sum(axis=1)
    return np.quantile(means,[.025,.975]).tolist()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',default=Path('output'),type=Path);a=p.parse_args()
    before=fingerprint(a.input);raw=load(a.input);signals,legacy,checks=extract(raw);rows=[r for r in signals if r['overnight_quality']]
    full=[r for r in signals if r['full_day_quality']];delayed=[r['delayed_one_minute'] for r in rows if r['delayed_one_minute'] is not None]
    masks={'toward':lambda r:r['movement']=='toward','away':lambda r:r['movement']=='away','unchanged':lambda r:r['movement']=='unchanged',
           'sunday':lambda r:pd.Timestamp(r['date']).weekday()==0,'other_weekdays':lambda r:pd.Timestamp(r['date']).weekday()!=0,
           'first_year':lambda r:r['date']<'2025-08-29','second_year':lambda r:r['date']>='2025-08-29',
           'away_first_year':lambda r:r['movement']=='away' and r['date']<'2025-08-29',
           'away_second_year':lambda r:r['movement']=='away' and r['date']>='2025-08-29'}
    result={'question':'Does fading an ES gap still open at 18:30 improve the trade?', 'source_sha256':before,'checks':checks,
            'first_morning_date':rows[0]['date'],'last_morning_date':rows[-1]['date'],'main':summary(rows),
            'groups':{name:summary([r for r in rows if test(r)]) for name,test in masks.items()},
            'signal_groups_before_outcome_quality':{name:sum(test(r) for r in signals) for name,test in masks.items()},
            'cost_scenarios':{str(c):stats([r['no_stop']-c for r in rows]) for c in [.5,1.,2.,4.]},
            'no_stop_net_mean_95_weekly_resampling':weekly_range(rows),
            'resampling':{'unit':'Monday–Sunday week of morning date','draws':10000,'seed':SEED,'selection_adjusted':False},
            'full_day':{'events':len(full),'touches_before_0930':sum(r.get('touch',False) for r in full),'touches_before_1700':sum(r['full_day_touch'] for r in full),
                        'net_one_point':stats([r['hold_to_1700']-1 for r in full]),
                        'same_events_0930_net':stats([r['no_stop']-1 for r in full if r['overnight_quality']])},
            'delayed_to_1831':{'net_one_point':stats([x-1 for x in delayed]),'excluded':len(rows)-len(delayed)},
            'legacy':{'events':len(legacy),'touches':sum(r['touch'] for r in legacy),
                      'shared_with_current':len(set(r['date'] for r in legacy)&set(r['date'] for r in rows)),
                      'old_events_not_in_current':sorted(set(r['date'] for r in legacy)-set(r['date'] for r in rows)),
                      'no_stop_net':stats([r['no_stop']-1 for r in legacy]),
                      'stop_1_net':stats([r['stop_1_distance']-1 for r in legacy]),'stop_2_net':stats([r['stop_2_distance']-1 for r in legacy])},
            'limitations':['Signal selection uses target and opening-window information only; later quality exclusions are outcome availability, not a real-time filter.',
                           'Entry at observed 18:30 open and target-touch fills are idealized; no order or quote validation.',
                           'Stops use adverse gap opens and pessimistic stop-first unresolved same-minute ties; no actual slippage model.',
                           'Same previously explored archive; movement groups, two stops, delays and periods are exploratory.']}
    assert fingerprint(a.input)==before;a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    aggregate=[{'group':name,'events':x['events'],'later_overnight_touches':x['touches'],'mean_no_stop_gross_points':x['rules']['no_stop']['gross']['mean'],'mean_no_stop_net_one_point':x['rules']['no_stop']['net_one_point']['mean']} for name,x in [('all',result['main']),*result['groups'].items()]]
    pd.DataFrame(aggregate).to_csv(a.output/'group_summary.csv',index=False)
    print(json.dumps({k:result[k] for k in ['checks','main','legacy','full_day','delayed_to_1831']},indent=2))

if __name__=='__main__':main()
