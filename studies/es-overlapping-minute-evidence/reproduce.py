"""Recalculate two fixed examples of overlapping windows and unequal day weights."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
PACKAGE=Path(__file__).resolve().parent
CFG=json.loads((PACKAGE/'analysis-config.json').read_text(encoding='utf-8'))

def mean_by_slot(values,valid,slot):
    n=np.bincount(slot[valid],minlength=1380);s=np.bincount(slot[valid],weights=values[valid],minlength=1380)
    return np.divide(s,n,out=np.full(1380,np.nan),where=n>0)

def average(close,segment,n,kind):
    result=np.full(len(close),np.nan);starts=np.r_[0,np.flatnonzero(np.diff(segment))+1];ends=np.r_[starts[1:],len(close)]
    for a,b in zip(starts,ends):
        x=close[a:b]
        if len(x)<n:continue
        c=np.r_[0.,np.cumsum(x)];total=c[n:]-c[:-n]
        if kind=='SMA':value=total/n
        else:
            weighted=np.r_[0.,np.cumsum(x*np.arange(1,len(x)+1))];end=np.arange(n,len(x)+1);start=end-n;value=((weighted[end]-weighted[start])-start*total)/(n*(n+1)/2)
        result[a+n-1:b]=value
    return result

def resample(count,effect,seed,reps):
    rng=np.random.default_rng(seed);ix=rng.integers(len(count),size=(reps,len(count)));n=count[ix];a=effect[ix]
    return np.quantile((n*a).sum(axis=1)/n.sum(axis=1),[.025,.975]),np.quantile(a.mean(axis=1),[.025,.975])

def seed_for(case,period):return int.from_bytes(hashlib.sha256(f"{CFG['random_seed']}|{case}|{period}".encode()).digest()[:8],'little')

def greedy_count(indices,segment,h):
    count=0;last=-h;lastseg=None
    for i in indices:
        if segment[i]!=lastseg or i-last>=h:count+=1;last=int(i);lastseg=segment[i]
    return count

def summarize(case,pname,indices,excess,day,segment,h):
    dates,inv=np.unique(day[indices],return_inverse=True);n=np.bincount(inv);a=np.bincount(inv,weights=excess)/n
    minute=np.mean(excess);equal=np.mean(a);cov=np.mean((n-n.mean())*(a-equal));mi,di=resample(n,a,seed_for(case,pname),CFG['bootstrap_repetitions'])
    gap=np.diff(indices);same=segment[indices[1:]]==segment[indices[:-1]];pairs=int(np.sum(same&(gap<h)));top=max(1,int(np.ceil(len(n)*.1)))
    return {'case':case,'period':pname,'horizon':h,'observations':len(indices),'signal_days':len(n),'mean_signals_per_day':n.mean(),'median_signals_per_day':float(np.median(n)),'minimum_signals_per_day':int(n.min()),'maximum_signals_per_day':int(n.max()),'top_tenth_days_count':top,'top_tenth_days_signal_share_pct':100*np.sort(n)[-top:].sum()/n.sum(),'equal_minute_extra_bp':minute,'equal_day_extra_bp':equal,'weighting_gap_bp':minute-equal,'count_effect_covariance':cov,'covariance_divided_mean_count_bp':cov/n.mean(),'minute_day_block_low_bp':mi[0],'minute_day_block_high_bp':mi[1],'equal_day_block_low_bp':di[0],'equal_day_block_high_bp':di[1],'successive_signal_pairs':max(0,len(indices)-1),'overlapping_successive_pairs':pairs,'overlapping_successive_pairs_pct':100*pairs/max(1,len(indices)-1),'greedy_nonoverlapping_windows':greedy_count(indices,segment,h)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,default=PACKAGE/'results');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    assert hashlib.sha256(args.input.read_bytes()).hexdigest()==CFG['source_sha256'],'Unexpected source fingerprint'
    f=pq.read_table(args.input,columns=['timestamp_utc','close','roll_transition','is_complete','quality_state','price_source']).to_pandas().sort_values('timestamp_utc',kind='stable');f=f.loc[f.is_complete.fillna(False)].reset_index(drop=True)
    seg=f.roll_transition.fillna(False).cumsum().to_numpy();loc=pd.DatetimeIndex(f.timestamp_utc).tz_convert('America/New_York');slot=((loc.hour.to_numpy()-18)%24)*60+loc.minute.to_numpy();keep=slot<1380
    audit={'source_file':args.input.name,'sha256':CFG['source_sha256'],'complete_source_rows':len(f),'range_utc':[str(f.timestamp_utc.min()),str(f.timestamp_utc.max())],'maintenance_rows_removed':int((~keep).sum()),'duplicate_timestamps':int(f.timestamp_utc.duplicated().sum()),'roll_transitions':int(f.roll_transition.sum()),'quality_states':f.quality_state.value_counts().to_dict(),'price_sources':f.price_source.value_counts().to_dict()}
    f=f.loc[keep].reset_index(drop=True);seg=seg[keep];slot=slot[keep];loc=loc[keep];day=np.array((loc.normalize()+pd.to_timedelta((loc.hour>=18).astype(int),unit='D')).date,dtype='datetime64[D]').astype('int64');year=pd.DatetimeIndex(day.astype('datetime64[D]')).year.to_numpy();period=np.select([year<=2014,year<=2022,year<=2024],['HISTORICAL','DISCOVERY','VALIDATION'],default='LATER');close=f.close.to_numpy(float)
    assert not f.timestamp_utc.duplicated().any();assert np.isfinite(close).all() and (close>0).all();gaps=np.diff(pd.DatetimeIndex(f.timestamp_utc).to_numpy(dtype='datetime64[m]').astype('int64'));audit.update(eligible_rows=len(f),trading_dates=int(np.unique(day).size),gaps_over_one_minute=int((gaps>1).sum()),largest_gap_minutes=int(gaps.max()))
    (args.output/'data-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8');rows=[]
    for spec in CFG['cases']:
        name=spec['id'];h=spec['horizon'];k=spec['slope_bars'];ma=average(close,seg,spec['length'],spec['average']);lag=np.r_[np.full(k,np.nan),ma[:-k]];signal=(close<ma)&(ma<lag)&np.r_[np.zeros(k,bool),seg[k:]==seg[:-k]]
        future=np.r_[close[h:],np.full(h,np.nan)];valid=np.r_[(seg[h:]==seg[:-h])&(period[h:]==period[:-h]),np.zeros(h,bool)];ret=10000*spec['direction']*(future-close)/close
        for pname in ['HISTORICAL','DISCOVERY','VALIDATION','LATER']:
            universe=valid&(period==pname);ix=np.flatnonzero(universe&signal);base=mean_by_slot(ret,universe,slot);ex=ret[ix]-base[slot[ix]];rows.append(summarize(name,pname,ix,ex,day,seg,h))
        print('Recalculated '+name,flush=True)
    pd.DataFrame(rows).to_csv(args.output/'weighting-and-overlap.csv',index=False,float_format='%.12g');assert hashlib.sha256(args.input.read_bytes()).hexdigest()==CFG['source_sha256'];print('Methods calculation complete',flush=True)

if __name__=='__main__':main()
