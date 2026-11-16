
"""Portable saved-forecast analysis. No model or private application imports."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parent
KEY=['variant','symbol','model','lookback','target_date']

def load(path,timing):
    cfg=json.loads((BASE/'config.json').read_text())
    for p,h in [(path,cfg['input_sha256']),(timing,cfg['timing_sha256'])]:
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('Input fingerprint differs')
    d=pd.read_csv(path,float_precision='round_trip');t=pd.DataFrame(json.loads(timing.read_text()))
    if d.duplicated(KEY).any() or t.duplicated(KEY).any():raise ValueError('Duplicate forecast key')
    expected={(s,m,n) for s in cfg['specs'] for m,n in cfg['settings']}
    assert set(zip(d.symbol,d.model,d.lookback))==expected and set(d.variant)==set(cfg['seeds'])
    cols=['previous_close','actual_open','actual_high','actual_low','actual_close','predicted_open','predicted_high','predicted_low','predicted_close']
    assert np.isfinite(d[cols].to_numpy()).all()
    assert (d.actual_high>=d[['actual_open','actual_close','actual_low']].max(axis=1)).all() and (d.actual_low<=d[['actual_open','actual_close','actual_high']].min(axis=1)).all()
    d['direction']=np.sign(d.predicted_close-d.previous_close).astype(int);d['actual_sign']=np.sign(d.actual_close-d.previous_close).astype(int)
    mult=d.symbol.map({s:v[1] for s,v in cfg['specs'].items()});tick=d.symbol.map({s:v[0] for s,v in cfg['specs'].items()})
    d['new_cost']=np.where(d.direction!=0,5+2*tick*mult,0);d['new_gross']=(d.direction*(d.actual_close-d.actual_open)*mult).round(2);d['new_net']=(d.new_gross-d.new_cost).round(2)
    d['new_long']=((d.actual_close-d.actual_open)*mult-5-2*tick*mult).round(2);d['new_short']=((d.actual_open-d.actual_close)*mult-5-2*tick*mult).round(2)
    d['error']=abs(d.predicted_close-d.actual_close);d['base_error']=abs(d.previous_close-d.actual_close)
    d['invalid']=(d.predicted_high<d[['predicted_open','predicted_low','predicted_close']].max(axis=1))|(d.predicted_low>d[['predicted_open','predicted_high','predicted_close']].min(axis=1))
    for a,b in [('new_net','net_usd'),('new_cost','cost_usd'),('new_gross','gross_usd'),('direction','bias'),('new_long','always_long_net_usd'),('new_short','always_short_net_usd')]:assert np.allclose(d[a],d[b],atol=1e-8,rtol=0),(a,b)
    hist=d[(d.phase=='history')&(d.target_date>=cfg['historical_first'])&(d.target_date<=cfg['historical_last'])].copy();forward=d[d.phase=='forward'].copy()
    assert len(d)==43494 and len(hist)==43098 and len(forward)==264 and set(forward.target_date)==set(cfg['forward_dates'])
    f=forward.merge(t,on=KEY,validate='one_to_one',suffixes=('','_forecast'));assert len(f)==264
    assert (pd.to_datetime(f.created_at_utc_forecast,utc=True)<pd.to_datetime(f.target_open_utc,utc=True)).all()
    return cfg,d,hist,forward

def series(frame):
    out=[]
    for k,g in frame.groupby(['variant','symbol','model','lookback'],sort=True):
        g=g.sort_values('target_date');net=g.new_net.to_numpy();eq=np.r_[0,net.cumsum()];directional=g.actual_sign!=0;err=float(g.error.mean());be=float(g.base_error.mean())
        out.append(dict(zip(['variant','symbol','model','lookback'],k))|dict(days=len(g),first_date=g.target_date.min(),last_date=g.target_date.max(),trades=int((g.direction!=0).sum()),correct=int((g.direction[directional]==g.actual_sign[directional]).sum()),direction_days=int(directional.sum()),net_usd=float(net.sum()),always_long_usd=float(g.new_long.sum()),always_short_usd=float(g.new_short.sum()),net_without_best5_usd=float(net.sum()-np.sort(net)[-5:].sum()),net_double_cost_usd=float((g.new_net-g.new_cost).sum()),mean_error_points=err,baseline_error_points=be,error_reduction_percent=100*(1-err/be) if be else None,invalid_candles=int(g.invalid.sum()),max_closed_drawdown_usd=float((np.maximum.accumulate(eq)-eq).max()),net_2025_usd=float(g.loc[g.target_date<'2026-01-01','new_net'].sum()),net_2026_usd=float(g.loc[g.target_date>='2026-01-01','new_net'].sum())))
    return pd.DataFrame(out)

def calculate(path,timing):
    cfg,d,h,f=load(path,timing);ss=series(h);fs=series(f);settings=[];quality=[];agreement=[]
    for (symbol,model,n),g in ss.groupby(['symbol','model','lookback'],sort=True):
        assert len(g)==3
        settings.append(dict(symbol=symbol,model=model,lookback=int(n),days_per_seed=int(g.days.min()),mean_net_usd=float(g.net_usd.mean()),min_net_usd=float(g.net_usd.min()),max_net_usd=float(g.net_usd.max()),always_long_usd=float(g.always_long_usd.iloc[0]),always_short_usd=float(g.always_short_usd.iloc[0]),positive_seeds=int((g.net_usd>0).sum()),beats_long_seeds=int((g.net_usd>g.always_long_usd).sum()),beats_short_seeds=int((g.net_usd>g.always_short_usd).sum()),mean_net_without_best5_usd=float(g.net_without_best5_usd.mean()),mean_error_reduction_percent=float(g.error_reduction_percent.mean())))
    for symbol,g in h.groupby('symbol',sort=True):
        a=ss[ss.symbol==symbol];quality.append(dict(symbol=symbol,worse_series=int((a.error_reduction_percent<0).sum()),series=len(a),forecast_rows=len(g),invalid_candles=int(g.invalid.sum())))
    pivot=h.pivot(index=['symbol','model','lookback','target_date'],columns='variant',values='direction');assert pivot.notna().all().all();unanimous=pivot.nunique(axis=1)==1
    for k,g in unanimous.groupby(level=['symbol','model','lookback']):agreement.append(dict(zip(['symbol','model','lookback'],k))|dict(unanimous=int(g.sum()),matched_days=len(g)))
    intervals=[];rng=np.random.default_rng(cfg['bootstrap']['seed'])
    for symbol,model,n in cfg['bootstrap']['selected_settings']:
        x=h[(h.symbol==symbol)&(h.model==model)&(h.lookback==n)].groupby('target_date')[['new_net','new_long','new_short']].mean().sort_index();days=len(x)
        for baseline in ['new_long','new_short']:
            values=(x.new_net-x[baseline]).to_numpy()
            for block in cfg['bootstrap']['block_lengths']:
                starts=rng.integers(0,days,size=(10000,int(np.ceil(days/block))));indices=((starts[:,:,None]+np.arange(block))%days).reshape(10000,-1)[:,:days];boot=values[indices].mean(axis=1)
                intervals.append(dict(symbol=symbol,model=model,lookback=n,baseline='always_long' if baseline=='new_long' else 'always_short',block_days=block,days=days,mean_daily_advantage_usd=float(values.mean()),lower95_usd=float(np.quantile(boot,.025)),upper95_usd=float(np.quantile(boot,.975))))
    r=dict(snapshot_rows=len(d),history_rows=len(h),excluded_history_extension_rows=int(((d.phase=='history')&(d.target_date>cfg['historical_last'])).sum()),history_dates=[h.target_date.min(),h.target_date.max()],settings=len(settings),seed_series=len(ss),forward_rows=len(f),forward_dates=cfg['forward_dates'],forward_before_open=len(f),unanimous_groups=int(unanimous.sum()),matched_groups=len(pivot),invalid_candles=int(h.invalid.sum()),worse_price_series=int((ss.error_reduction_percent<0).sum()),market_quality=quality)
    return r,dict(settings=pd.DataFrame(settings),seeds=ss,forward=fs,agreement=pd.DataFrame(agreement),uncertainty=pd.DataFrame(intervals))

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--timing',type=Path,required=True);args=p.parse_args();r,t=calculate(args.input,args.timing)
    (BASE/'results.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    for name,df in t.items():df.to_csv(BASE/(name+'.csv'),index=False)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
