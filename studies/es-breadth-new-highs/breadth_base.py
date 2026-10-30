"""Closing breadth washouts and subsequent ES chart-price changes; aggregate outputs only."""
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

FILES={'es':'CME_MINI_ES1!, 1D_c578e.csv','b200':'INDEX_S5TH, D_0f94a.csv','b50':'INDEX_S5FI, D_96a6d.csv','b20':'INDEX_S5TW, D_dc629.csv','b5':'INDEX_S5FD, D_905a5.csv'}
LAST_COMPLETE='2026-10-01'
HORIZONS=[1,3,5,10]

def fingerprint(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def load(folder):
    frames={};checks={}
    for name,file in FILES.items():
        g=pd.read_csv(folder/file)
        assert g.time.is_monotonic_increasing and not g.time.duplicated().any()
        assert pd.to_datetime(g.time,format='%Y-%m-%d',errors='raise').notna().all()
        assert np.isfinite(g.close).all()
        if name=='es':
            assert np.isfinite(g[['open','high','low','close']].to_numpy()).all() and g[['open','high','low','close']].gt(0).all().all()
            assert (g.low.le(g[['open','close','high']].min(axis=1)) & g.high.ge(g[['open','close','low']].max(axis=1))).all()
        else:assert g.close.between(0,100).all()
        frames[name]=g.set_index('time');checks[name]={'rows':len(g),'first_date':g.time.min(),'last_date':g.time.max()}
    es=frames['es'].loc[:LAST_COMPLETE].copy();es['es_row']=np.arange(len(es))
    common=es.copy();matches={}
    for name,window in [('b200',200),('b50',50),('b20',20),('b5',5)]:
        common=common.join(frames[name].close.rename(name),how='inner')
        embedded=next(c for c in es.columns if f'Above {window}-Day' in c)
        paired=es[[embedded]].join(frames[name].close).dropna();assert np.allclose(paired[embedded],paired.close,rtol=0,atol=1e-9)
        matches[name]=len(paired)
    common=common.loc[common[['b200','b50','b20','b5']].notna().all(axis=1)].copy()
    common['year']=pd.to_datetime(common.index).year;common['weekday']=pd.to_datetime(common.index).weekday
    for h in HORIZONS:
        ret=100*(es.close.shift(-h)/es.open.shift(-1)-1)
        net=ret-100/es.open.shift(-1)  # one chart point assumed round-trip cost
        common[f'r{h}']=ret.reindex(common.index);common[f'n{h}']=net.reindex(common.index)
        common[f'entry{h}']=es.open.shift(-1).reindex(common.index)
        x=common.groupby(['year','weekday'])[f'r{h}'];total=x.transform('sum');n=x.transform('count')
        common[f'matched{h}']=(total-common[f'r{h}'])/(n-1)
    checks.update(es_complete_rows=len(es),excluded_developing_or_later_rows=len(frames['es'])-len(es),
                  common_dates=len(common),common_first=common.index.min(),common_last=common.index.max(),embedded_close_matches=matches)
    return common,checks

def spaced(frame,gap):
    rows=[];last=-10**9
    for position,source_row in enumerate(frame.es_row):
        if source_row>=last+gap:rows.append(position);last=source_row
    return frame.iloc[rows]

def describe(frame,h):
    g=frame.loc[frame[f'r{h}'].notna()];x=g[f'r{h}'];net=g[f'n{h}'];matched=g[f'matched{h}']
    if not len(g):return {'events':0}
    return {'events':len(g),'mean_pct':float(x.mean()),'median_pct':float(x.median()),'positive_events':int(x.gt(0).sum()),
            'positive_pct':float(100*x.gt(0).mean()),'mean_after_one_point_pct':float(net.mean()),
            'same_year_weekday_leave_one_out_mean_pct':float(matched.mean()),'mean_excess_pct_points':float((x-matched).mean()),
            'minimum_pct':float(x.min()),'maximum_pct':float(x.max()),'first_signal_date':g.index.min(),'last_signal_date':g.index.max()}
