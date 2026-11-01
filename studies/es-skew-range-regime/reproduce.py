"""Recheck SKEW closing rank and subsequent ES range; no trading-profit claim."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'analysis-config.json').read_text())
FILES={'es':'CME_MINI_ES1!, 1D_c578e.csv','skew':'CBOE_DLY_SKEW, 1W_a7232.csv'}
HORIZONS=[1,4]
def fingerprint(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rank(s):
    return s.rolling(105,min_periods=105).apply(lambda v:100*np.count_nonzero(v[:-1]<=v[-1])/104,raw=True)
def spaced(g,gap):
    chosen=[];last=-100000
    for i,w in enumerate(g.week_row):
        if w>=last+gap:chosen.append(i);last=w
    return g.iloc[chosen]
def prepare(folder):
    raw={};checks={};end=pd.Timestamp(CONFIG['last_complete_week_start'])
    for name,file in FILES.items():
        g=pd.read_csv(folder/file);dates=pd.to_datetime(g.time)
        assert dates.is_monotonic_increasing and dates.is_unique
        assert np.isfinite(g[['open','high','low','close']]).all().all() and g[['open','high','low','close']].gt(0).all().all()
        assert g.low.le(g[['open','close']].min(axis=1)).all() and g.high.ge(g[['open','close']].max(axis=1)).all()
        g.index=pd.DatetimeIndex(dates);g['week']=g.index-pd.to_timedelta(g.index.dayofweek,unit='D');raw[name]=g
        checks[name]={'rows':len(g),'first_date':g.time.iloc[0],'last_date':g.time.iloc[-1]}
    es=raw['es'];sk=raw['skew'];assert sk.week.is_unique
    daily_return=100*(es.close/es.close.shift(1)-1)
    es['vol']=daily_return.rolling(20,min_periods=20).std(ddof=1)
    sk=sk.loc[sk.week.le(end)].set_index('week')
    skgrid=sk.reindex(pd.date_range(sk.index.min(),end,freq='W-MON'))
    weekly=es.loc[es.week.le(end)].groupby('week').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),vol=('vol','last'),source_rows=('close','size'))
    weekly=weekly.reindex(pd.date_range(weekly.index.min(),end,freq='W-MON'))
    f=weekly.copy();f['rank']=rank(skgrid.close).reindex(f.index);f['reported_rank']=rank(sk.close).reindex(f.index)
    f['skew_close']=skgrid.close.reindex(f.index);f['week_row']=np.arange(len(f));f['year']=f.index.year
    f['vol_band']=np.searchsorted(CONFIG['volatility_band_edges_pct'],f.vol,side='right')-1
    for h in HORIZONS:
        exists=pd.concat([weekly.source_rows.shift(-j).notna() for j in range(1,h+1)],axis=1).all(axis=1)
        entry=weekly.open.shift(-1);exit=weekly.close.shift(-h)
        highs=pd.concat([weekly.high.shift(-j) for j in range(1,h+1)],axis=1).max(axis=1)
        lows=pd.concat([weekly.low.shift(-j) for j in range(1,h+1)],axis=1).min(axis=1)
        f[f'points{h}']=(highs-lows).where(exists)
        f[f'range{h}']=(100*(highs-lows)/entry).where(exists)
        f[f'direction{h}']=(100*(exit/entry-1)).where(exists)
    f=f.loc[f.open.notna()&f.skew_close.notna()].copy()
    checks.update(last_complete_week_start=str(end.date()),common_weeks=len(f),calendar_rank_available=int(f['rank'].notna().sum()),reported_rank_available=int(f.reported_rank.notna().sum()),missing_skew_weeks=[str(d.date()) for d in skgrid.index[skgrid.close.isna()]],holiday_labels_remapped=int((raw['skew'].index!=raw['skew'].week).sum()),excluded_es_developing_rows=int(es.week.gt(end).sum()),excluded_skew_developing_rows=int(raw['skew'].week.gt(end).sum()))
    f.index=f.index.strftime('%Y-%m-%d')
    return f,checks
def eligible(f,history):
    g=f.loc[f[history].notna()&f.vol.notna()].copy()
    g['group']=np.where(g[history].le(20),'low',np.where(g[history].ge(80),'high','middle'))
    for h in HORIZONS:
        count=g.groupby(['year','vol_band'])[f'range{h}'].transform('count')
        total=g.groupby(['year','vol_band'])[f'range{h}'].transform('sum')
        g[f'peers{h}']=count-g[f'range{h}'].notna().astype(int)
        g[f'matched{h}']=((total-g[f'range{h}'])/(count-1)).where((count>1)&g[f'range{h}'].notna())
    return g
def describe(g,h):
    g=g.loc[g[f'range{h}'].notna()];matched=g.loc[g[f'matched{h}'].notna()]
    if not len(g):return {'events':0}
    out={'events':len(g),'mean_range_pct':float(g[f'range{h}'].mean()),'median_range_pct':float(g[f'range{h}'].median()),'mean_range_points':float(g[f'points{h}'].mean()),'mean_direction_pct':float(g[f'direction{h}'].mean()),'positive_events':int(g[f'direction{h}'].gt(0).sum()),'positive_pct':float(100*g[f'direction{h}'].gt(0).mean()),'mean_trailing_daily_sd_pct':float(g.vol.mean()),'matched_events':len(matched),'unmatched_events':len(g)-len(matched),'first_signal_week':g.index.min(),'last_signal_week':g.index.max()}
    if len(matched):out.update(matched_signal_mean_range_pct=float(matched[f'range{h}'].mean()),peer_mean_range_pct=float(matched[f'matched{h}'].mean()),excess_range_pct_points=float((matched[f'range{h}']-matched[f'matched{h}']).mean()),minimum_peer_weeks=int(matched[f'peers{h}'].min()),median_peer_weeks=float(matched[f'peers{h}'].median()))
    return out
def calculate(f):
    results={};table=[]
    for history in ['rank','reported_rank']:
        g=eligible(f,history);detail={}
        for group in ['low','middle','high','all']:
            mask=g.group.eq(group) if group!='all' else pd.Series(True,index=g.index)
            chosen=g.loc[mask];first=g.loc[mask&~(mask.shift(1,fill_value=False)&g.week_row.diff().eq(1))]
            detail[group]={'signal_weeks':len(chosen),'first_run_weeks':len(first),'horizons':{}}
            for h in HORIZONS:
                valid=chosen.loc[chosen[f'range{h}'].notna()]
                methods={'all_weeks':valid,'first_consecutive_group_week':first,'nonoverlapping_by_horizon':spaced(valid,h)}
                detail[group]['horizons'][str(h)]={name:describe(rows,h) for name,rows in methods.items()}
                for name,d in detail[group]['horizons'][str(h)].items():table.append({'history':history,'group':group,'forward_calendar_weeks':h,'counting_method':name,**d})
        results[history]=detail
    main=eligible(f,'rank')
    periods={name:{group:{str(h):describe(main.loc[mask&(main.group.eq(group) if group!='all' else True)],h) for h in HORIZONS} for group in ['low','middle','high','all']} for name,mask in [('1997_2009',main.year.le(2009)),('2010_2019',main.year.between(2010,2019)),('2020_2026',main.year.ge(2020))]}
    return results,periods,pd.DataFrame(table)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True,type=Path);a=p.parse_args()
    before={name:fingerprint(a.input_dir/file) for name,file in FILES.items()};f,checks=prepare(a.input_dir);results,periods,table=calculate(f)
    assert before=={name:fingerprint(a.input_dir/file) for name,file in FILES.items()}
    out={'checked_date':'2026-10-16','config':CONFIG,'source_sha256':before,'checks':checks,'results':results,'periods':periods,'aggregate_rows':len(table)}
    target=HERE/'results';target.mkdir(exist_ok=True);(target/'summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8');table.to_csv(target/'range_summary.csv',index=False)
    print(json.dumps({'checks':checks,'primary':{g:results['rank'][g]['horizons'] for g in ['low','high']},'aggregate_rows':len(table)},indent=2))
if __name__=='__main__':main()
