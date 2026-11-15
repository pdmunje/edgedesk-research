"""Completed ten-minute runs; safe aggregate outputs and explicitly private bar cache."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
BASE=Path(__file__).resolve().parent
MINUTE=60_000_000_000; BLOCK=10*MINUTE; HOUR=60*MINUTE

def read_source(path,cfg):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    if h.hexdigest()!=cfg['input_sha256']:raise ValueError('Input fingerprint differs')
    cols=['timestamp_utc','open','high','low','close','underlying_contract','roll_transition','is_complete','quality_state','price_source']
    x=pq.read_table(path,columns=cols).to_pandas()
    ts=pd.DatetimeIndex(x['timestamp_utc']);ns=ts.to_numpy(dtype='datetime64[ns]').astype('int64')
    if ts.tz is None or np.any(np.diff(ns)<=0) or np.any(ns%MINUTE):raise ValueError('Timestamp contract')
    v=x[['open','high','low','close']].to_numpy(dtype=float)
    if not(np.isfinite(v).all() and (v>0).all() and (v[:,2]<=np.minimum(v[:,0],v[:,3])).all() and (v[:,1]>=np.maximum(v[:,0],v[:,3])).all()):raise ValueError('OHLC contract')
    seg=np.cumsum(x['roll_transition'].to_numpy(dtype=bool)).astype('int64')
    # Provided roll flags must separate every observed contract identity change.
    contract=x['underlying_contract'].astype(str).to_numpy()
    known=x['underlying_contract'].notna().to_numpy() & ~np.isin(contract,['','None','nan','<NA>'])
    if np.any(known[1:] & known[:-1] & (contract[1:]!=contract[:-1]) & (seg[1:]==seg[:-1])):raise ValueError('Unflagged known contract change')
    local=ts.tz_convert('America/New_York');maintenance=local.hour==17;complete=x['is_complete'].to_numpy(dtype=bool)
    keep=complete & ~maintenance & known
    audit=dict(input_rows=len(x),input_first=ts[0].isoformat(),input_last=ts[-1].isoformat(),incomplete_source_rows=int((~complete).sum()),maintenance_rows=int((complete&maintenance).sum()),unknown_contract_rows=int((complete & ~maintenance & ~known).sum()),retained_minutes=int(keep.sum()),roll_flags=int(x['roll_transition'].sum()),quality_counts={str(k):int(v) for k,v in x['quality_state'].value_counts().items()},price_source_counts={str(k):int(v) for k,v in x['price_source'].value_counts().items()})
    audit['retained_first']=ts[keep][0].isoformat();audit['retained_last']=ts[keep][-1].isoformat();audit['retained_quality_counts']={str(k):int(v) for k,v in x.loc[keep,'quality_state'].value_counts().items()}
    df=pd.DataFrame({'ns':ns[keep],'o':v[keep,0],'h':v[keep,1],'l':v[keep,2],'c':v[keep,3],'seg':seg[keep]})
    df['bucket']=df['ns']//BLOCK
    return df,audit

def aggregate(df):
    grouped=df.groupby('bucket',sort=True).agg(ns=('ns','first'),last=('ns','last'),n=('ns','size'),o=('o','first'),h=('h','max'),l=('l','min'),c=('c','last'),seg=('seg','first'),segments=('seg','nunique'))
    expected=grouped.index.to_numpy()*BLOCK
    good=(grouped['n'].to_numpy()==10)&(grouped['ns'].to_numpy()==expected)&(grouped['last'].to_numpy()==expected+9*MINUTE)&(grouped['segments'].to_numpy()==1)
    audit=dict(observed_ten_minute_groups=len(grouped),rejected_ten_minute_groups=int((~good).sum()),complete_ten_minute_groups=int(good.sum()))
    return grouped.loc[good].reset_index(drop=True),audit

def label_dates(ns):
    local=pd.to_datetime(ns,utc=True).tz_convert('America/New_York')
    naive=local.tz_localize(None).normalize()+pd.to_timedelta((local.hour>=18).astype(int),unit='D')
    return np.asarray(naive.strftime('%Y-%m-%d'),dtype='U10'),np.asarray(local.hour)

def construct(g):
    ns=g['ns'].to_numpy();o=g['o'].to_numpy();h=g['h'].to_numpy();l=g['l'].to_numpy();c=g['c'].to_numpy();seg=g['seg'].to_numpy()
    breaks=np.r_[True,(np.diff(ns)!=BLOCK)|(np.diff(seg)!=0)]
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.r_[np.nan,c[:-1]]),np.abs(l-np.r_[np.nan,c[:-1]])))
    tr[breaks]=np.nan
    prev6=pd.Series(tr).shift(1).rolling(6,min_periods=6).sum().to_numpy()
    large=np.isfinite(tr)&np.isfinite(prev6)&(3*tr>=prev6)
    colour=np.sign(c-o).astype(int)
    starts=np.flatnonzero(breaks|np.r_[True,colour[1:]!=colour[:-1]]|(colour==0))
    ends=np.r_[starts[1:]-1,len(g)-1]
    # Hour coverage is independent of the event definition.
    hd=g.assign(hourkey=ns//HOUR).groupby('hourkey',sort=True).agg(first=('ns','first'),last=('ns','last'),n=('ns','size'),segments=('seg','nunique'))
    hk=hd.index.to_numpy();good=(hd['n'].to_numpy()==6)&(hd['first'].to_numpy()==hk*HOUR)&(hd['last'].to_numpy()==hk*HOUR+5*BLOCK)&(hd['segments'].to_numpy()==1)
    hours=hk[good];td,clock=label_dates(hours*HOUR)
    records=[];unsupported=0;detected=0
    supported=set(hours.tolist())
    for s,e in zip(starts,ends):
        n=e-s+1;d=colour[s]
        if not d or n<2:continue
        q=s+1 if large[s] and large[s+1] else s+2 if n>=3 else None
        if q is None:continue
        detected+=1;hourkey=(int(ns[q])+BLOCK)//HOUR
        if hourkey not in supported:unsupported+=1;continue
        full=d*(c[e]-o[s])/.25;done=d*(c[q]-o[s])/.25;remaining=d*(c[e]-c[q])/.25
        records.append((s,e,q,hourkey,d,n,full,done,remaining,(e-q)*10,int(e+1==len(g) or breaks[e+1])))
    ev=np.asarray(records,dtype=float)
    return dict(ns=ns,o=o,h=h,l=l,c=c,seg=seg,tr=tr,large=large,colour=colour,breaks=breaks,hours=hours,hour_td=td,hour_clock=clock,events=ev),dict(detected_confirmed_runs=detected,runs_outside_complete_confirmation_hour=unsupported,retained_runs=len(ev),eligible_hours=len(hours),observed_hour_groups=len(hd),excluded_hour_groups=int((~good).sum()))

def summarize(a,cfg):
    ev=a['events'];hours=a['hours'];td=a['hour_td'];clock=a['hour_clock'];hours_index={int(h):i for i,h in enumerate(hours)}
    ei=np.asarray([hours_index[int(h)] for h in ev[:,3]],dtype=int);event_rows=[];hour_rows=[]
    def metrics(x):
        return dict(events=len(x),mean_full_ticks=float(np.mean(x[:,6])),median_full_ticks=float(np.median(x[:,6])),mean_completed_ticks=float(np.mean(x[:,7])),mean_remaining_ticks=float(np.mean(x[:,8])),median_remaining_ticks=float(np.median(x[:,8])),no_further_same_colour_bar=int((x[:,9]==0).sum()),mean_observed_minutes=float(np.mean(x[:,5]*10)),boundary_ended_runs=int(x[:,10].sum()),full_negative=int((x[:,6]<0).sum()))
    for phase in cfg['phases']:
        hm=np.ones(len(hours),dtype=bool) if phase=='All' else td<'2020-01-01' if phase=='Before 2020' else td>='2020-01-01'
        ep=hm[ei]
        for kind in ['All qualifying runs','Two-bar large pair','At least three same-colour bars']:
            m=ep & (np.ones(len(ev),dtype=bool) if kind=='All qualifying runs' else ev[:,5]==2 if kind=='Two-bar large pair' else ev[:,5]>=3)
            event_rows.append(dict(phase=phase,kind=kind,**metrics(ev[m])))
        for hour in range(24):
            eligible=hm&(clock==hour)
            if not eligible.any():continue
            em=ep&(clock[ei]==hour);x=ev[em];n=int(eligible.sum());with_event=len(set(ev[em,3].astype('int64')))
            hour_rows.append(dict(phase=phase,confirmation_hour_NY=f'{hour:02d}:00–{(hour+1)%24:02d}:00',eligible_hours=n,hours_with_event=with_event,hour_event_percent=100*with_event/n,events=len(x),events_per_100_hours=100*len(x)/n,mean_full_ticks=float(np.mean(x[:,6])) if len(x) else None,mean_remaining_ticks=float(np.mean(x[:,8])) if len(x) else None))
    return event_rows,hour_rows

def calculate(path):
    cfg=json.loads((BASE/'config.json').read_text());df,audit=read_source(path,cfg);g,agg=aggregate(df);a,coverage=construct(g);er,hr=summarize(a,cfg)
    return dict(audit={**audit,**agg,**coverage},event_summary=er,hour_summary=hr),a

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);ap.add_argument('--private-cache',required=True,type=Path);args=ap.parse_args()
    if args.private_cache.resolve().is_relative_to(BASE):raise ValueError('Private cache must be outside public study directory')
    args.private_cache.mkdir(parents=True,exist_ok=True)
    r,a=calculate(args.input);np.savez_compressed(args.private_cache/'bar-event-cache.npz',**a)
    (BASE/'results.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for filename,key in [('event-summary','event_summary'),('hour-summary','hour_summary')]:pd.DataFrame(r[key]).to_csv(BASE/(filename+'.csv'),index=False)
    print(json.dumps({'audit':r['audit'],'events':r['event_summary'],'top_earlier_hours':sorted([x for x in r['hour_summary'] if x['phase']=='Before 2020'],key=lambda x:-x['hour_event_percent'])[:3]},indent=2))
if __name__=='__main__':main()
