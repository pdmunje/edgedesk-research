"""Opening-range sweep research: original replay, strict execution check, plain control."""
import argparse,hashlib,json,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import legacy
PACKAGE=Path(__file__).resolve().parent;CFG=json.loads((PACKAGE/'analysis-config.json').read_text(encoding='utf-8'))

def source(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==CFG['source_sha256'],'Unexpected source fingerprint'
    cols=['timestamp_utc','open','high','low','close','underlying_contract','roll_transition','is_complete','quality_state','price_source']
    d=pq.read_table(path,columns=cols).to_pandas().sort_values('timestamp_utc',kind='stable');d=d.loc[d.is_complete.fillna(False)].reset_index(drop=True);d['source_segment']=d.roll_transition.fillna(False).cumsum();loc=pd.DatetimeIndex(d.timestamp_utc).tz_convert('America/New_York');d['session_minute']=((loc.hour.to_numpy()-18)%24)*60+loc.minute.to_numpy();d['session_date']=(loc.normalize()+pd.to_timedelta((loc.hour>=18).astype(int),unit='D')).date;keep=d.session_minute<1380
    audit={'source_file':path.name,'sha256':CFG['source_sha256'],'complete_rows':len(d),'range_utc':[str(d.timestamp_utc.min()),str(d.timestamp_utc.max())],'maintenance_rows_removed':int((~keep).sum()),'roll_transitions':int(d.roll_transition.sum()),'duplicates':int(d.timestamp_utc.duplicated().sum()),'quality_states':d.quality_state.value_counts().to_dict(),'price_sources':d.price_source.value_counts().to_dict()}
    d=d.loc[keep].reset_index(drop=True);assert not d.timestamp_utc.duplicated().any();assert np.isfinite(d[['open','high','low','close']]).all().all();assert (d.low<=d[['open','close']].min(axis=1)).all() and (d.high>=d[['open','close']].max(axis=1)).all() and (d.low>0).all();audit['eligible_session_rows']=len(d)
    return d,audit

def strict_history(p,x,family):
    p=p.copy();segments=x.groupby('parent_id',sort=False).source_segment.agg(['nunique','first']);p['segment_count']=p.parent_id.map(segments['nunique']);p['segment']=p.parent_id.map(segments['first']);p['full']=(p['count']==p.duration)&(p.first_min==p.start)&(p.last_min==p.end-1)&(p.contract_count==1)&(p.segment_count==1)
    if family=='4H':p=p.loc[p.duration==240].copy()
    for n in CFG['atr_lengths']:
        prior=np.full(len(p),np.nan);history=[];value=np.nan;last_segment=None;previous=None
        for j,row in enumerate(p.itertuples(index=False)):
            if not row.full:history=[];value=np.nan;previous=None;last_segment=None;continue
            if row.segment!=last_segment:history=[];value=np.nan;previous=None
            prior[j]=value;tr=max(row.high-row.low,abs(row.high-previous),abs(row.low-previous)) if previous is not None else row.high-row.low;history.append(tr)
            if len(history)==n:value=float(np.mean(history))
            elif len(history)>n:value=(value*(n-1)+tr)/n
            previous=row.close;last_segment=row.segment
        p[f'strict_atr{n}_prior']=prior
    return p

def strict_trade(q,meta,opening,atr_n,side,sweep):
    atr=meta[f'strict_atr{atr_n}_prior']
    if not meta['full'] or not np.isfinite(atr) or atr<=0:return None,False
    m=q.session_minute.to_numpy();start=int(meta['start']);op=q.open.to_numpy();hi=q.high.to_numpy();lo=q.low.to_numpy();cl=q.close.to_numpy();mask=m<start+opening;upper=hi[mask].max();lower=lo[mask].min();post=np.flatnonzero(m>=start+opening);seen=False;entry=None
    for j in post:
        breaks=cl[j]>upper if side=='long' else cl[j]<lower
        if breaks and (seen or not sweep):entry=j+1;break
        seen=seen or (lo[j]<=lower if side=='long' else hi[j]>=upper)
    if entry is None or entry>=len(q):return None,True
    raw=min(meta['open'],upper-atr) if side=='long' else max(meta['open'],lower+atr);stop=np.floor(raw/.25+1e-10)*.25 if side=='long' else np.ceil(raw/.25-1e-10)*.25;price=op[entry];risk=price-stop if side=='long' else stop-price
    # Explicit benchmark cancellation: no order when the next open is at/beyond its planned stop.
    if risk<=0:return None,True
    exit_price=cl[-1];stopped=False
    for j in range(entry,len(q)):
        if (lo[j]<=stop if side=='long' else hi[j]>=stop):exit_price=min(op[j],stop) if side=='long' else max(op[j],stop);stopped=True;break
    gross=exit_price-price if side=='long' else price-exit_price
    return (float(gross),stopped),True

def period(year):return np.select([year<=2015,year<=2022],['historical_2010_2015','development_2016_2022'],default='later_2023_2026')

def interval(values,day,seed,reps):
    frame=pd.DataFrame({'day':day,'value':values}).groupby('day').value.agg(['sum','count']).to_numpy();rng=np.random.default_rng(seed);ix=rng.integers(len(frame),size=(reps,len(frame)));draw=frame[ix];return np.quantile(draw[:,:,0].sum(1)/draw[:,:,1].sum(1),[.025,.975])

def key_seed(key):return int.from_bytes(hashlib.sha256((str(CFG['seed'])+'|'+key).encode()).digest()[:8],'little')

def fingerprints(gross,eligible,stopped):
    return {name:hashlib.sha256(values.tobytes()).hexdigest() for name,values in [('gross',np.nan_to_num(np.round(gross,8),nan=1e12).astype('<f8')),('eligible',eligible.astype('u1')),('stopped',stopped.astype('u1'))]}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,default=PACKAGE/'results');args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True);d,audit=source(args.input);(out/'data-audit.json').write_text(json.dumps(audit,indent=2)+'\n');rows=[];annual=[];comparisons=[];parents=[];prints={}
    for family,ors in CFG['or_lengths'].items():
        print('Replaying '+family,flush=True);x=legacy.add_parent_ids(d,family);p=legacy.parent_table(x);ps=strict_history(p,x,family).set_index('parent_id',drop=False);p=p.set_index('parent_id',drop=False);specs=list(itertools.product(ors,CFG['atr_lengths'],['long','short']));mapping={tuple(v):j for j,v in enumerate(specs)};shape=(len(p),len(specs));gross={model:np.full(shape,np.nan) for model in ['legacy_sweep','strict_sweep','strict_plain']};stops={model:np.zeros(shape,bool) for model in gross};eligible=np.zeros(shape,bool);index={pid:j for j,pid in enumerate(p.index)}
        for pid,q in x.groupby('parent_id',sort=False,observed=True):
            i=index[pid];meta=p.loc[pid]
            if family!='4H' or meta.duration==240:
                for event in legacy.simulate_parent(q,meta,ors):j=mapping[(event['or_minutes'],event['atr_length'],event['side'])];gross['legacy_sweep'][i,j]=event['gross_points'];stops['legacy_sweep'][i,j]=event['stopped']
            if pid not in ps.index:continue
            strict=ps.loc[pid]
            for j,(opening,n,side) in enumerate(specs):
                for model,sweep in [('strict_sweep',True),('strict_plain',False)]:
                    trade,ok=strict_trade(q,strict,opening,n,side,sweep);eligible[i,j]=ok
                    if trade is not None:gross[model][i,j]=trade[0];stops[model][i,j]=trade[1]
        day=np.array(p.session_date,dtype='datetime64[D]').astype('int64');year=pd.DatetimeIndex(np.array(p.session_date,dtype='datetime64[D]')).year.to_numpy();labels=period(year);parents.append({'family':family,'source_parents':len(p),'legacy_90pct_parents':int(((p.coverage>=.9)&(p.contract_count==1)&(p.first_min==p.start)&(p.last_min>=p.end-2)&((p.duration==240) if family=='4H' else True)).sum()),'strict_complete_parents':int(ps['full'].sum()),'strict_atr9_eligible':int((ps['full']&ps.strict_atr9_prior.notna()).sum()),'strict_atr14_eligible':int((ps['full']&ps.strict_atr14_prior.notna()).sum())})
        for model in ['strict_sweep','strict_plain']:prints[family+'|'+model]=fingerprints(gross[model],eligible,stops[model])
        for j,(opening,n,side) in enumerate(specs):
            for model in gross:
                values=gross[model][:,j];valid=np.isfinite(values)
                for pname in CFG['periods']:
                    m=valid if pname=='all_2010_2026' else valid&(labels==pname);net=values[m]-CFG['cost_points'];key=f'{family}|{opening}|{n}|{side}|{model}|{pname}';ci=interval(net,day[m],key_seed(key),CFG['bootstrap_repetitions']) if m.any() else [np.nan,np.nan]
                    rows.append({'family':family,'or_minutes':opening,'atr_length':n,'side':side,'model':model,'period':pname,'trades':int(m.sum()),'signal_days':int(np.unique(day[m]).size),'gross_avg_points':float(np.mean(values[m])) if m.any() else np.nan,'net_avg_points':float(np.mean(net)) if m.any() else np.nan,'net_win_pct':100*float(np.mean(net>0)) if m.any() else np.nan,'stop_pct':100*float(np.mean(stops[model][m,j])) if m.any() else np.nan,'net_ci_low':ci[0],'net_ci_high':ci[1]})
                for yy in sorted(set(year)):
                    m=valid&(year==yy);annual.append({'family':family,'or_minutes':opening,'atr_length':n,'side':side,'model':model,'year':int(yy),'trades':int(m.sum()),'net_avg_points':float(np.mean(values[m]-CFG['cost_points'])) if m.any() else np.nan})
            sweep=np.where(np.isfinite(gross['strict_sweep'][:,j]),gross['strict_sweep'][:,j]-CFG['cost_points'],0);plain=np.where(np.isfinite(gross['strict_plain'][:,j]),gross['strict_plain'][:,j]-CFG['cost_points'],0)
            for pname in CFG['periods']:
                e=eligible[:,j] if pname=='all_2010_2026' else eligible[:,j]&(labels==pname);delta=sweep[e]-plain[e];ci=interval(delta,day[e],key_seed(f'paired|{family}|{opening}|{n}|{side}|{pname}'),CFG['bootstrap_repetitions']) if e.any() else [np.nan,np.nan]
                comparisons.append({'family':family,'or_minutes':opening,'atr_length':n,'side':side,'period':pname,'eligible_parents':int(e.sum()),'sweep_trades':int(np.isfinite(gross['strict_sweep'][e,j]).sum()),'plain_trades':int(np.isfinite(gross['strict_plain'][e,j]).sum()),'sweep_net_per_parent':float(sweep[e].mean()) if e.any() else np.nan,'plain_net_per_parent':float(plain[e].mean()) if e.any() else np.nan,'sweep_minus_plain_per_parent':float(delta.mean()) if e.any() else np.nan,'difference_ci_low':ci[0],'difference_ci_high':ci[1]})
        print('Finished '+family,flush=True)
    for name,data in [('summary.csv',rows),('annual.csv',annual),('paired-comparison.csv',comparisons),('parent-eligibility.csv',parents)]:pd.DataFrame(data).to_csv(out/name,index=False,float_format='%.12g')
    (out/'strict-fingerprints.json').write_text(json.dumps(prints,indent=2)+'\n');assert hashlib.sha256(args.input.read_bytes()).hexdigest()==CFG['source_sha256'];print('Full fixed grid complete',flush=True)

if __name__=='__main__':main()
