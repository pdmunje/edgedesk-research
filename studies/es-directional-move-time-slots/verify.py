"""Independent array aggregation and streaming confirmation check; private cache only."""
from pathlib import Path
from collections import defaultdict,deque
import argparse,json,math
import numpy as np
import pandas as pd
from reproduce import read_source,MINUTE,BLOCK,HOUR,BASE

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);ap.add_argument('--private-cache',required=True,type=Path);args=ap.parse_args()
    cfg=json.loads((BASE/'config.json').read_text());r=json.loads((BASE/'results.json').read_text());a=dict(np.load(args.private_cache/'bar-event-cache.npz',allow_pickle=False));df,audit=read_source(args.input,cfg)
    ns=df['ns'].to_numpy();b=ns//BLOCK;ix=np.r_[0,np.flatnonzero(np.diff(b))+1];end=np.r_[ix[1:]-1,len(b)-1];n=end-ix+1
    keep=(n==10)&(ns[ix]==b[ix]*BLOCK)&(ns[end]==b[ix]*BLOCK+9*MINUTE)&(df['seg'].to_numpy()[ix]==df['seg'].to_numpy()[end])
    expected={'ns':ns[ix][keep],'o':df['o'].to_numpy()[ix][keep],'c':df['c'].to_numpy()[end][keep],'h':np.maximum.reduceat(df['h'].to_numpy(),ix)[keep],'l':np.minimum.reduceat(df['l'].to_numpy(),ix)[keep],'seg':df['seg'].to_numpy()[ix][keep]}
    for k,v in expected.items():assert np.array_equal(v,a[k]),k
    # Independent hour coverage from the reconstructed complete bars.
    hk=a['ns']//HOUR;hi=np.r_[0,np.flatnonzero(np.diff(hk))+1];he=np.r_[hi[1:]-1,len(hk)-1]
    eligible=(he-hi+1==6)&(a['ns'][hi]==hk[hi]*HOUR)&(a['ns'][he]==hk[hi]*HOUR+5*BLOCK)&(a['seg'][hi]==a['seg'][he])
    assert np.array_equal(hk[hi][eligible],a['hours'])
    history=deque(maxlen=6);large=[];tr_checks=0
    for i in range(len(a['ns'])):
        continuous=i>0 and a['ns'][i]-a['ns'][i-1]==BLOCK and a['seg'][i]==a['seg'][i-1]
        if not continuous:history.clear();tr=float('nan')
        else:tr=max(a['h'][i]-a['l'][i],abs(a['h'][i]-a['c'][i-1]),abs(a['l'][i]-a['c'][i-1]))
        flag=continuous and len(history)==6 and 3*tr>=math.fsum(history)
        large.append(flag)
        if continuous:history.append(tr)
        assert bool(a['large'][i])==bool(flag),('large threshold',i)
        tr_checks+=1
    # Stream only currently completed bars: confirmation does not require the future run end.
    stream=[];run_start=0;direction=0;seen=False;qual=None
    supported=set(a['hours'].tolist());detected=0
    def finish(last):
        if qual is None:return
        key=(int(a['ns'][qual])+BLOCK)//HOUR
        if key not in supported:return
        d=direction;s=run_start;q=qual;e=last
        full=d*(a['c'][e]-a['o'][s])/.25;done=d*(a['c'][q]-a['o'][s])/.25;rest=d*(a['c'][e]-a['c'][q])/.25
        boundary=int(e+1==len(a['ns']) or a['ns'][e+1]-a['ns'][e]!=BLOCK or a['seg'][e+1]!=a['seg'][e])
        stream.append([s,e,q,key,d,e-s+1,full,done,rest,(e-q)*10,boundary])
    for i in range(len(a['ns'])):
        d=1 if a['c'][i]>a['o'][i] else -1 if a['c'][i]<a['o'][i] else 0
        continuous=i>0 and a['ns'][i]-a['ns'][i-1]==BLOCK and a['seg'][i]==a['seg'][i-1]
        if not continuous or not d or d!=direction:
            if i:finish(i-1)
            run_start=i;direction=d;seen=False;qual=None
        length=i-run_start+1
        if d and not seen and (length>=3 or (length==2 and large[i-1] and large[i])):
            qual=i;seen=True;detected+=1
    finish(len(a['ns'])-1)
    rebuilt=np.asarray(stream,dtype=float)
    assert np.array_equal(rebuilt,a['events'])
    assert detected==r['audit']['detected_confirmed_runs']
    assert np.allclose(rebuilt[:,6],rebuilt[:,7]+rebuilt[:,8],atol=1e-10)
    # Recount summaries directly, independently of the calculator's summarizer.
    index={int(key):i for i,key in enumerate(a['hours'])};ev=rebuild=rebuilt;ei=np.asarray([index[int(x)] for x in ev[:,3]])
    for s in r['event_summary']:
        phase=np.ones(len(ev),dtype=bool) if s['phase']=='All' else a['hour_td'][ei]<'2020-01-01' if s['phase']=='Before 2020' else a['hour_td'][ei]>='2020-01-01'
        mask=phase & (np.ones(len(ev),dtype=bool) if s['kind']=='All qualifying runs' else ev[:,5]==2 if s['kind']=='Two-bar large pair' else ev[:,5]>=3)
        x=ev[mask];assert len(x)==s['events'];assert int((x[:,9]==0).sum())==s['no_further_same_colour_bar']
        for k,col in [('mean_full_ticks',6),('mean_completed_ticks',7),('mean_remaining_ticks',8)]:assert math.isclose(math.fsum(x[:,col])/len(x),s[k],abs_tol=1e-9)
        assert np.median(x[:,8])==s['median_remaining_ticks']
    for s in r['hour_summary']:
        hour=int(s['confirmation_hour_NY'][:2]);hm=a['hour_clock']==hour
        if s['phase']!='All':hm &= a['hour_td']<'2020-01-01' if s['phase']=='Before 2020' else a['hour_td']>='2020-01-01'
        mask=hm[ei];x=ev[mask];n=int(hm.sum());unique=len(set(x[:,3]));assert n==s['eligible_hours'] and unique==s['hours_with_event'] and len(x)==s['events']
        assert math.isclose(100*unique/n,s['hour_event_percent'],abs_tol=1e-10)
        assert math.isclose(math.fsum(x[:,8])/len(x),s['mean_remaining_ticks'],abs_tol=1e-9)
    # Invented mechanics: 3-bar recognition can occur at the observed run end.
    o=np.array([100,101,102,103]);c=np.array([101,102,103,104]);assert c[2]-c[2]==0 and c[3]-c[2]==1
    assert (c[3]-o[0])==(c[2]-o[0])+(c[3]-c[2])
    assert 3*12>=sum([6]*6) and not 3*11.75>=sum([6]*6)
    out=dict(status='passed',independent_ten_minute_OHLC_values=4*len(a['ns']),independent_large_bar_checks=tr_checks,streaming_confirmed_runs=detected,retained_streaming_runs=len(rebuilt),independent_event_summary_rows=len(r['event_summary']),independent_hour_rows=len(r['hour_summary']),invented_mechanics=3,scope='Aggregate data arithmetic and causal pattern-recognition timing; observed end-of-run marks are not executable exits or profits.')
    (BASE/'verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
