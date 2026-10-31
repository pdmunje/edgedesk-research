"""Weekly SKEW declines and later ES chart-price changes; aggregate output only."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'analysis-config.json').read_text())
FILES={'es':'CME_MINI_ES1!, 1D_c578e.csv','skew':'CBOE_DLY_SKEW, 1W_a7232.csv'}
HORIZONS=CONFIG['forward_horizons_calendar_weeks']

def fingerprint(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def monday(dates):return dates-pd.to_timedelta(dates.weekday,unit='D')
def standardized(changes):
    previous=changes.shift(1).rolling(104,min_periods=104)
    mean=previous.mean();sd=previous.std(ddof=1)
    return (changes-mean)/sd.where(sd.gt(0))

def load(folder):
    raw={};checks={}
    for name,file in FILES.items():
        g=pd.read_csv(folder/file);dates=pd.to_datetime(g.time,format='%Y-%m-%d',errors='raise')
        assert dates.is_monotonic_increasing and dates.is_unique
        assert np.isfinite(g[['open','high','low','close']].to_numpy()).all()
        assert g[['open','high','low','close']].gt(0).all().all()
        assert g.low.le(g[['open','close','high']].min(axis=1)).all() and g.high.ge(g[['open','close','low']].max(axis=1)).all()
        g.index=pd.DatetimeIndex(dates);g['week']=monday(g.index);raw[name]=g
        checks[name]={'rows':len(g),'first_source_date':g.time.iloc[0],'last_source_date':g.time.iloc[-1]}
    end=pd.Timestamp(CONFIG['last_complete_week_start']);es=raw['es'];sk=raw['skew']
    assert sk.week.is_unique
    complete_sk=sk.loc[sk.week.le(end)].set_index('week');full_sk=complete_sk.reindex(pd.date_range(complete_sk.index.min(),end,freq='W-MON'))
    change=full_sk.close-full_sk.open;z=standardized(change)
    complete_es=es.loc[es.week.le(end)]
    weekly=complete_es.groupby('week').agg(open=('open','first'),close=('close','last'),source_rows=('close','size'))
    grid=pd.date_range(weekly.index.min(),end,freq='W-MON');weekly=weekly.reindex(grid)
    f=weekly.join(full_sk[['open','close']].rename(columns={'open':'skew_open','close':'skew_close'}))
    f['change']=change.reindex(f.index);f['z']=z.reindex(f.index)
    f['z_reported_observations']=standardized(complete_sk.close-complete_sk.open).reindex(f.index)
    f['week_row']=np.arange(len(f));f['year']=f.index.year
    for h in HORIZONS:
        valid=pd.concat([weekly.source_rows.shift(-j).notna() for j in range(1,h+1)],axis=1).all(axis=1)
        entry=weekly.open.shift(-1);exit=weekly.close.shift(-h)
        f[f'r{h}']=(100*(exit/entry-1)).where(valid)
        f[f'n{h}']=(100*(exit-entry-1)/entry).where(valid)
        f[f'entry{h}']=entry.where(valid)
    f=f.loc[f.skew_open.notna()&f.open.notna()].copy()
    for h in HORIZONS:
        group=f.groupby('year')[f'r{h}'];f[f'matched{h}']=(group.transform('sum')-f[f'r{h}'])/(group.transform('count')-1)
    checks.update(last_complete_week_start=str(end.date()),excluded_ES_rows_in_developing_week=int(es.week.gt(end).sum()),excluded_skew_developing_rows=int(sk.week.gt(end).sum()),holiday_week_labels_remapped=int((sk.index!=sk.week).sum()),missing_skew_calendar_weeks=[str(d.date()) for d in full_sk.index[full_sk.open.isna()]],common_signal_weeks=len(f),common_first=str(f.index.min().date()),common_last=str(f.index.max().date()),normalized_available_signal_weeks=int(f.z.notna().sum()))
    f.index=f.index.strftime('%Y-%m-%d')
    return f,checks

def spaced(g,gap):
    indices=[];last=-10**9
    for position,row in enumerate(g.week_row):
        if row>=last+gap:indices.append(position);last=row
    return g.iloc[indices]

def describe(frame,h):
    g=frame.loc[frame[f'r{h}'].notna()];x=g[f'r{h}'];matched=g[f'matched{h}']
    if not len(g):return {'events':0}
    return {'events':len(g),'mean_pct':float(x.mean()),'median_pct':float(x.median()),'positive_events':int(x.gt(0).sum()),'positive_pct':float(100*x.gt(0).mean()),'mean_after_one_point_pct':float(g[f'n{h}'].mean()),'same_year_other_week_mean_pct':float(matched.mean()),'mean_excess_pct_points':float((x-matched).mean()),'minimum_pct':float(x.min()),'maximum_pct':float(x.max()),'first_signal_week':g.index.min(),'last_signal_week':g.index.max()}

def signals(f):
    return {**{f'change_le{abs(k)}':f.change.le(k) for k in CONFIG['fixed_change_cutoffs_points']},'normalized_le1_5':f.z.le(CONFIG['normalized_cutoff'])}

def calculate(f):
    results={};rows=[]
    for name,signal in signals(f).items():
        # A missing calendar week interrupts a consecutive run, even if absent from f.
        prior=signal.shift(1,fill_value=False)&f.week_row.diff().eq(1)
        first=f.loc[signal&~prior];all_weeks=f.loc[signal]
        detail={'signal_weeks':len(all_weeks),'consecutive_signal_runs':len(first),'horizons':{}}
        for h in HORIZONS:
            available=all_weeks.loc[all_weeks[f'r{h}'].notna()]
            methods={'all_signal_weeks':available,'first_consecutive_signal_week':first,'nonoverlapping':spaced(available,h),'four_week_spacing':spaced(available,4),'eight_week_spacing':spaced(available,8)}
            detail['horizons'][str(h)]={m:describe(g,h) for m,g in methods.items()}
            for m,d in detail['horizons'][str(h)].items():rows.append({'condition':name,'forward_calendar_weeks':h,'counting_method':m,**d})
        results[name]=detail
    return results,pd.DataFrame(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,required=True);a=p.parse_args()
    before={k:fingerprint(a.input_dir/v) for k,v in FILES.items()};f,checks=load(a.input_dir);results,table=calculate(f)
    periods={period:{name:{str(h):describe(f.loc[mask&signal],h) for h in HORIZONS} for name,signal in [('fixed_le5',f.change.le(-5)),('normalized_le1_5',f.z.le(-1.5)),('all_weeks',pd.Series(True,index=f.index)),('normalized_eligible',f.z.notna())]} for period,mask in [('1997_2009',f.year.le(2009)),('2010_2019',f.year.between(2010,2019)),('2020_2026',f.year.ge(2020))]}
    history_audit={'previous104_calendar_weeks':{str(h):describe(f.loc[f.z.le(-1.5)],h) for h in HORIZONS},'previous104_reported_observations':{str(h):describe(f.loc[f.z_reported_observations.le(-1.5)],h) for h in HORIZONS},'reported_observation_history_eligible_weeks':int(f.z_reported_observations.notna().sum())}
    out={'checked_date':'2026-10-16','config':CONFIG,'source_sha256':before,'checks':checks,'baseline':{str(h):describe(f,h) for h in HORIZONS},'normalized_eligible_baseline':{str(h):describe(f.loc[f.z.notna()],h) for h in HORIZONS},'results':results,'periods':periods,'normalization_history_audit':history_audit,'aggregate_rows':len(table)}
    assert before=={k:fingerprint(a.input_dir/v) for k,v in FILES.items()}
    output=HERE/'results';output.mkdir(exist_ok=True);(output/'summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8');table.to_csv(output/'weekly_change_summary.csv',index=False)
    print(json.dumps({'checks':checks,'primary':{name:{h:{m:{k:d[k] for k in ['events','mean_pct','positive_events']} for m,d in methods.items()} for h,methods in results[name]['horizons'].items()} for name in ['change_le5','normalized_le1_5']},'aggregate_rows':len(table)},indent=2))
if __name__=='__main__':main()
