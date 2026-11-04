"""Empirical short-window discovery for ES forward long distributions."""
from __future__ import annotations

import argparse, gc, hashlib, json
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PACKAGE=Path(__file__).resolve().parent
HERE=PACKAGE/'results'
CFG=json.loads((PACKAGE/'analysis-config.json').read_text(encoding='utf-8'))
FIXED=json.loads((PACKAGE/'frozen-definitions.json').read_text(encoding='utf-8'))
FIXED_NAMES={x['candidate'] for v in FIXED.values() for x in (v['qualified'] or v['top_diagnostics'][:1])}
SRC=None
def remember(states,name,state,kind,w,sh,fam):
    if name in FIXED_NAMES:states[name]=(state.copy(),kind,w,sh,fam)
def row_seed(name,period,h):
    return int.from_bytes(hashlib.sha256(f"{CFG['random_seed']}|{name}|{period}|{h}".encode()).digest()[:8],'little')



def log(x): print(x,flush=True)
def rsum(x,n):
    o=np.full(x.size,np.nan);c=np.r_[0.,np.cumsum(x,dtype=float)];o[n-1:]=c[n:]-c[:-n];return o
def sma(x,n): return rsum(x,n)/n
def wma(x,n):
    o=np.full(x.size,np.nan);i=np.arange(1,x.size+1,dtype=float);c=np.r_[0.,np.cumsum(x)];ci=np.r_[0.,np.cumsum(x*i)];e=np.arange(n,x.size+1);s=e-n
    o[n-1:]=((ci[e]-ci[s])-s*(c[e]-c[s]))/(n*(n+1)/2);return o
def ema(x,n): return pd.Series(x,copy=False).ewm(span=n,adjust=False,min_periods=n).mean().to_numpy()
def segmented(x,seg,n,kind):
    out=np.full(x.size,np.nan);starts=np.r_[0,np.flatnonzero(seg[1:]!=seg[:-1])+1];ends=np.r_[starts[1:],x.size];fn={"SMA":sma,"EMA":ema,"WMA":wma}[kind]
    for a,b in zip(starts,ends):
        if b-a>=n: out[a:b]=fn(x[a:b],n)
    return out
def extreme(x,h,maximum):
    out=np.full(x.size,np.nan);q=deque();cmp=(lambda a,b:a>=b) if maximum else (lambda a,b:a<=b)
    for j in range(1,x.size):
        while q and cmp(x[j],x[q[-1]]):q.pop()
        q.append(j);t=j-h
        if t>=0:
            while q and q[0]<=t:q.popleft()
            if q:out[t]=x[q[0]]
    return out
def baseline(y,mask,minute):
    ok=mask&np.isfinite(y);s=np.bincount(minute[ok],weights=y[ok],minlength=1380);n=np.bincount(minute[ok],minlength=1380)
    return np.divide(s,n,out=np.full(1380,np.nan),where=n>0)
def day_effect(y,state,emask,minute,day,base,seed):
    m=state&emask&np.isfinite(y);ex=y[m]-base[minute[m]];u,inv=np.unique(day[m],return_inverse=True);daily=np.bincount(inv,weights=ex)/np.bincount(inv)
    if len(daily)==0:return np.nan,np.nan,np.nan
    RNG=np.random.default_rng(seed);boot=np.mean(daily[RNG.integers(0,len(daily),(CFG["bootstrap_repetitions"],len(daily)))],axis=1)
    return float(np.mean(daily)),float(np.quantile(boot,.025)),float(np.quantile(boot,.975))
def summarize(name,family,kind,w,sh,state,period,emask,minute,day,year,outcomes,bases):
    rows=[]
    for h in CFG["forward_horizons"]:
        ret=outcomes[h]["ret"];m=state&emask&np.isfinite(ret);b=bases[(period,h,"ret")];pb=bases[(period,h,"pos")];dm,lo,hi=day_effect(ret,state,emask,minute,day,b,row_seed(name,period,h))
        r=ret[m];mfe=outcomes[h]["mfe"][m];mae=outcomes[h]["mae"][m];tf=outcomes[h]["tf"][m]
        rows.append({"candidate":name,"family":family,"average_type":kind,"window":w,"slope_horizon":sh,"period":period,"forward_horizon":h,
          "coverage_pct":100*m.sum()/max(1,np.sum(emask&np.isfinite(ret))),"observations":int(m.sum()),"trading_days":int(np.unique(day[m]).size),"years":int(np.unique(year[m]).size),
          "positive_pct":100*np.mean(r>0),"baseline_positive_pct":100*np.nanmean(pb[minute[m]]),"excess_positive_pp":100*(np.mean(r>0)-np.nanmean(pb[minute[m]])),
          "mean_return_pct":100*np.mean(r),"baseline_mean_return_pct":100*np.nanmean(b[minute[m]]),"excess_mean_bp":10000*np.mean(r-b[minute[m]]),
          "day_balanced_excess_bp":10000*dm,"day_block_ci_low_bp":10000*lo,"day_block_ci_high_bp":10000*hi,
          "mean_MFE_points":np.mean(mfe),"mean_MAE_points":np.mean(mae),"MFE_MAE_ratio":np.mean(mfe)/np.mean(mae),
          "target_first_pct":100*np.mean(tf==1),"stop_first_pct":100*np.mean(tf==-1),"no_touch_pct":100*np.mean(tf==0),"ambiguous_first_touch_pct":100*np.mean(tf==3),"median_return_pct":100*np.median(r),**{f"p{q}_return_pct":100*np.quantile(r,q/100) for q in [10,25,75,90]}})
    return rows
def grouped_quintiles(score,edges,emask,h,minute,outcomes,bases,period):
    q=np.full(score.size,-1,np.int8);ok=np.isfinite(score);q[ok]=np.searchsorted(edges,score[ok],side="right")+1;ret=outcomes[h]["ret"];b=bases[(period,h,"ret")];m=emask&np.isfinite(ret)&(q>0);ex=ret[m]-b[minute[m]]
    sums=np.bincount(q[m],weights=ex,minlength=6);cnt=np.bincount(q[m],minlength=6);means=np.divide(sums[1:6],cnt[1:6],out=np.full(5,np.nan),where=cnt[1:6]>0)*10000
    probs=[];pb=bases[(period,h,"pos")]
    for k in range(1,6):
        z=m&(q==k);probs.append(100*(np.mean(ret[z]>0)-np.nanmean(pb[minute[z]])))
    rho=float(np.corrcoef(np.arange(5),means)[0,1]);correct=np.mean(np.diff(means)>=0);label="clear" if rho>=.9 and correct>=.75 else "approximate" if rho>=.6 else "weak" if rho>=.25 else "non-monotonic"
    return means,np.array(probs),rho,label
def main():
    global SRC,HERE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--output',type=Path,default=HERE);args=p.parse_args();SRC=args.input;HERE=args.output;HERE.mkdir(parents=True,exist_ok=True)
    assert hashlib.sha256(SRC.read_bytes()).hexdigest()==CFG['source_sha256'],'Unexpected source fingerprint'
    log('Reading licensed minute data')
    cols=['timestamp_utc','open','high','low','close','roll_transition','is_complete','quality_state','price_source','underlying_contract']
    d=pq.read_table(SRC,columns=cols).to_pandas().sort_values('timestamp_utc',kind='stable');d=d[d.is_complete.fillna(False)].reset_index(drop=True)
    segments=np.cumsum(d.roll_transition.fillna(False).to_numpy(bool));ts=pd.DatetimeIndex(d.timestamp_utc);loc=ts.tz_convert('America/New_York');slot=((loc.hour.to_numpy()-18)%24)*60+loc.minute.to_numpy();keep=slot<1380
    audit={'source_file':SRC.name,'sha256':CFG['source_sha256'],'complete_source_rows':len(d),'range_utc':[str(ts.min()),str(ts.max())],'maintenance_rows_removed':int((~keep).sum()),'duplicate_timestamps':int(ts.duplicated().sum()),'roll_transitions':int(d.roll_transition.sum()),'quality_states':d.quality_state.value_counts().to_dict(),'price_sources':d.price_source.value_counts().to_dict()}
    d=d.loc[keep].reset_index(drop=True);seg=segments[keep];ts=pd.DatetimeIndex(d.timestamp_utc);loc=ts.tz_convert('America/New_York');minute=slot[keep];valid=np.ones(len(d),bool)
    dates=(loc.normalize()+pd.to_timedelta((loc.hour>=18).astype(int),unit='D')).date;day=np.array(dates,dtype='datetime64[D]').astype(np.int64);year=np.array([x.year for x in dates])
    period=np.select([year<=2014,year<=2022,year<=2024],['HISTORICAL','DISCOVERY','VALIDATION'],default='HOLDOUT')
    close=d.close.to_numpy(float);high=d.high.to_numpy(float);low=d.low.to_numpy(float)
    assert not ts.duplicated().any();assert np.isfinite(d[['open','high','low','close']]).all().all();assert (d.low<=d[['open','close']].min(axis=1)).all() and (d.high>=d[['open','close']].max(axis=1)).all() and (d.low>0).all()
    gaps=np.diff(ts.to_numpy(dtype='datetime64[m]').astype('int64'));audit.update(eligible_rows=len(d),timestamp_gaps_over_1m=int((gaps>1).sum()),largest_gap_minutes=int(gaps.max()),missing_wallclock_minutes=int(np.maximum(gaps-1,0).sum()),session_slots=int(np.unique(minute).size),trading_dates=int(np.unique(day).size))
    (HERE/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    log("Computing forward long outcomes")
    outcomes={}
    for h in CFG["forward_horizons"]:
        same=np.r_[(seg[h:]==seg[:-h])&(period[h:]==period[:-h]),np.zeros(h,bool)];fc=np.r_[close[h:],np.full(h,np.nan)];fmax=extreme(high,h,True);fmin=extreme(low,h,False);ok=valid&same&np.isfinite(fc);ret=(fc-close)/close;ret[~ok]=np.nan;mfe=np.maximum(fmax-close,0);mae=np.maximum(close-fmin,0);mfe[~ok]=np.nan;mae[~ok]=np.nan
        rt=(mfe>=8)&ok;rs=(mae>=6.25)&ok;tf=np.zeros(len(d),np.int8);tf[rt&~rs]=1;tf[rs&~rt]=-1;active=rt&rs;target=close+8;stop=close-6.25
        for k in range(1,h+1):
            idx=np.flatnonzero(active[:-k]);fi=idx+k;ht=high[fi]>=target[idx];hs=low[fi]<=stop[idx];tf[idx[ht&~hs]]=1;tf[idx[hs&~ht]]=-1;tf[idx[ht&hs]]=3;active[idx[ht|hs]]=False
        tf[~ok]=2;outcomes[h]={"ret":ret,"mfe":mfe,"mae":mae,"tf":tf}
    masks={p:period==p for p in ("DISCOVERY","VALIDATION","HOLDOUT","HISTORICAL")};bases={}
    for p in ("DISCOVERY","VALIDATION"):
        m=masks[p]
        for h in CFG["forward_horizons"]:
            ret=outcomes[h]["ret"];bases[(p,h,"ret")]=baseline(ret,m,minute);bases[(p,h,"pos")]=baseline((ret>0).astype(float),m&np.isfinite(ret),minute)
    rows=[];monos=[];states={}
    log("Scanning predeclared short windows")
    for w in CFG["windows"]:
        log(f"Scanning window {w}")
        # Both signs are searched so continuation and mean reversion have equal opportunity.
        mom=np.full(len(d),np.nan);same=np.r_[np.zeros(w,bool),seg[w:]==seg[:-w]];mom[w:]=(close[w:]-close[:-w])/close[w:];mom[~same]=np.nan
        for sign,state in (("positive",mom>0),("negative",mom<0)):
            name=f"MOM{w}_{sign}";fam=f"momentum_{sign}";remember(states,name,state,"MOM",w,0,fam)
            for p in ("DISCOVERY","VALIDATION"):rows+=summarize(name,fam,"MOM",w,0,state,p,masks[p],minute,day,year,outcomes,bases)
        edges=np.quantile(mom[masks["DISCOVERY"]&np.isfinite(mom)],[.2,.4,.6,.8])
        for h in CFG["forward_horizons"]:
            for p in ("DISCOVERY","VALIDATION"):
                means,probs,rho,label=grouped_quintiles(mom,edges,masks[p],h,minute,outcomes,bases,p);monos.append({"signal":f"MOM{w}","family":"momentum","window":w,"average_type":"MOM","slope_horizon":0,"period":p,"forward_horizon":h,"monotonicity":label,"bucket_index_correlation":rho,**{f"Q{i+1}_excess_mean_bp":means[i] for i in range(5)},**{f"Q{i+1}_excess_probability_pp":probs[i] for i in range(5)}})
        for kind in CFG["average_types"]:
            ma=segmented(close,seg,w,kind);dist=(close-ma)/close
            for sign,state in (("above",close>ma),("below",close<ma)):
                name=f"{kind}{w}_{sign}";fam=f"price_{sign}_average";remember(states,name,state,kind,w,0,fam)
                for p in ("DISCOVERY","VALIDATION"):rows+=summarize(name,fam,kind,w,0,state,p,masks[p],minute,day,year,outcomes,bases)
            edges=np.quantile(dist[masks["DISCOVERY"]&np.isfinite(dist)],[.2,.4,.6,.8])
            for h in CFG["forward_horizons"]:
                for p in ("DISCOVERY","VALIDATION"):
                    means,probs,rho,label=grouped_quintiles(dist,edges,masks[p],h,minute,outcomes,bases,p);monos.append({"signal":f"{kind}{w}_distance","family":"average_distance","window":w,"average_type":kind,"slope_horizon":0,"period":p,"forward_horizon":h,"monotonicity":label,"bucket_index_correlation":rho,**{f"Q{i+1}_excess_mean_bp":means[i] for i in range(5)},**{f"Q{i+1}_excess_probability_pp":probs[i] for i in range(5)}})
            for sh in CFG["slope_horizons"]:
                sl=np.full(len(d),np.nan);same=np.r_[np.zeros(sh,bool),seg[sh:]==seg[:-sh]];sl[sh:]=ma[sh:]-ma[:-sh];sl[~same]=np.nan
                for sign,st in (("bull",(close>ma)&(sl>0)),("bear",(close<ma)&(sl<0))):
                    nm=f"{kind}{w}_slope{sh}_{sign}";fam=f"average_level_slope_{sign}";remember(states,nm,st,kind,w,sh,fam)
                    for p in ("DISCOVERY","VALIDATION"):rows+=summarize(nm,fam,kind,w,sh,st,p,masks[p],minute,day,year,outcomes,bases)
            del ma,dist;gc.collect()
        del mom;gc.collect()
    scan=pd.DataFrame(rows);scan.to_csv(HERE/"window_scan.csv",index=False);pd.DataFrame(monos).to_csv(HERE/"signal_quintiles.csv",index=False)
    # Freeze candidates independently by horizon. Gates are fixed in config; plateau requires neighboring windows in the same family/type/slope.
    frozen={};g=CFG["materiality_gates"]
    for h in CFG["forward_horizons"]:
        z=scan[scan.forward_horizon==h].pivot_table(index=["candidate","family","average_type","window","slope_horizon"],columns="period",values=["excess_mean_bp","excess_positive_pp","day_balanced_excess_bp","coverage_pct"])
        records=[]
        for idx,r in z.dropna().iterrows():
            name,fam,kind,w,sh=idx;ok=(r[("excess_mean_bp","DISCOVERY")]>=g["minimum_excess_mean_bp"] and r[("excess_mean_bp","VALIDATION")]>=g["minimum_excess_mean_bp"] and r[("excess_positive_pp","DISCOVERY")]>=g["minimum_excess_probability_pp"] and r[("excess_positive_pp","VALIDATION")]>=g["minimum_excess_probability_pp"] and r[("day_balanced_excess_bp","VALIDATION")]>0 and r[("coverage_pct","VALIDATION")]>=g["minimum_coverage_pct"])
            peers=z.reset_index();peers=peers[(peers.family==fam)&(peers.average_type==kind)&(peers.slope_horizon==sh)];near=peers[(peers.window!=w)&(abs(np.log(peers.window/w))<=np.log(2))];npos=int(np.sum((near[("excess_mean_bp","DISCOVERY")]>0)&(near[("excess_mean_bp","VALIDATION")]>0)))
            ok=ok and npos>=g["minimum_positive_neighbor_windows"];score=min(r[("excess_mean_bp","DISCOVERY")],r[("excess_mean_bp","VALIDATION")])+min(r[("excess_positive_pp","DISCOVERY")],r[("excess_positive_pp","VALIDATION")])*.1
            records.append((ok,score,name,fam,kind,int(w),int(sh),npos))
        qualified=sorted([x for x in records if x[0]],reverse=True);diagnostic=sorted(records,key=lambda x:x[1],reverse=True)[:5]
        frozen[str(h)]={"qualified":[{"candidate":x[2],"family":x[3],"average_type":x[4],"window":x[5],"slope_horizon":x[6],"positive_neighbors":x[7],"score":x[1]} for x in qualified[:3]],"top_diagnostics":[{"candidate":x[2],"family":x[3],"average_type":x[4],"window":x[5],"slope_horizon":x[6],"positive_neighbors":x[7],"score":x[1]} for x in diagnostic]}
    (HERE/"selection-audit.json").write_text(json.dumps(frozen,indent=2),encoding="utf-8")
    frozen=FIXED
    log("Evaluating unchanged earlier definitions on already examined later and historical dates")
    for p in ("HOLDOUT","HISTORICAL"):
        m=masks[p]
        for h in CFG["forward_horizons"]:
            ret=outcomes[h]["ret"];bases[(p,h,"ret")]=baseline(ret,m,minute);bases[(p,h,"pos")]=baseline((ret>0).astype(float),m&np.isfinite(ret),minute)
    finals=[]
    for h in CFG["forward_horizons"]:
        chosen=frozen[str(h)]["qualified"] or frozen[str(h)]["top_diagnostics"][:1]
        for spec in chosen:
            state,kind,w,sh,fam=states[spec["candidate"]]
            for p in ("DISCOVERY","VALIDATION","HOLDOUT","HISTORICAL"):
                rr=summarize(spec["candidate"],fam,kind,w,sh,state,p,masks[p],minute,day,year,outcomes,bases)
                finals += [x for x in rr if x["forward_horizon"]==h]
    final=pd.DataFrame(finals);final.to_csv(HERE/"frozen_candidate_results.csv",index=False)
    annual=[]
    for h in CFG["forward_horizons"]:
        chosen=frozen[str(h)]["qualified"] or frozen[str(h)]["top_diagnostics"][:1]
        for spec in chosen:
            state,kind,w,sh,fam=states[spec["candidate"]]
            for yy in sorted(np.unique(year)):
                if yy<2010:continue
                rr=summarize(spec["candidate"],fam,kind,w,sh,state,str(yy),year==yy,minute,day,year,outcomes,{(str(yy),hh,k):baseline((outcomes[hh]["ret"]>0).astype(float) if k=="pos" else outcomes[hh]["ret"],(year==yy)&(np.isfinite(outcomes[hh]["ret"]) if k=="pos" else True),minute) for hh in CFG["forward_horizons"] for k in ("ret","pos")})
                annual += [x for x in rr if x["forward_horizon"]==h]
    pd.DataFrame(annual).to_csv(HERE/"annual_stability.csv",index=False)
    assert hashlib.sha256(SRC.read_bytes()).hexdigest()==CFG['source_sha256']
    log('Full short-window scan and fixed-rule summaries complete')

if __name__=="__main__":main()
