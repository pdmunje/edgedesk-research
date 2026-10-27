"""Development-only time/side selection; aggregate outputs, licensed inputs excluded."""
import argparse,itertools,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import engine as e
P=Path(__file__).resolve().parent
C=e.CFG

def select(grid):
    dev=grid.loc[(grid.period=='development_2016_2022')&(grid.trades>=C['minimum_development_trades'])].copy()
    return dev.sort_values(['net_avg_points','trades','or_minutes','atr_length'],ascending=[False,False,True,True],kind='stable').groupby(['model','family','slot','side'],sort=True).head(1)

def summarize(values,stops,days,key):
    good=np.isfinite(values);x=values[good];net=x-C['cost_points'];count=len(net)
    ci=e.interval(net,days[good],e.key_seed(key),C['bootstrap_repetitions']) if count else [np.nan,np.nan]
    return dict(trades=count,signal_days=len(np.unique(days[good])),gross_avg_points=float(x.mean()) if count else np.nan,net_avg_points=float(net.mean()) if count else np.nan,net_sum_points=float(net.sum()),net_positive_trades=int((net>0).sum()),stopped_trades=int(stops[good].sum()),net_ci_low=ci[0],net_ci_high=ci[1])

def main():
    a=argparse.ArgumentParser();a.add_argument('--input',required=True,type=Path);a.add_argument('--output',type=Path,default=P/'results');a.add_argument('--private-cache',required=True,type=Path,help='Temporary local outcomes, outside any public study directory. Never distribute.');args=a.parse_args()
    assert not args.private_cache.resolve().is_relative_to(P.parents[1].resolve()),'Keep temporary outcomes outside the public research repository'
    args.output.mkdir(parents=True,exist_ok=True);args.private_cache.mkdir(parents=True,exist_ok=True)
    d,audit=e.source(args.input);rows=[];hashes={};expected=json.loads((P/'reference-fingerprints.json').read_text())
    for family,ors in C['or_lengths'].items():
        print('Replaying time/side grid: '+family,flush=True)
        x=e.legacy.add_parent_ids(d,family);p=e.legacy.parent_table(x).set_index('parent_id',drop=False);ps=e.strict_history(p.reset_index(drop=True),x,family).set_index('parent_id',drop=False)
        specs=list(itertools.product(ors,C['atr_lengths'],['long','short']));mapping={t:j for j,t in enumerate(specs)};index={pid:i for i,pid in enumerate(p.index)};shape=(len(p),len(specs));gross={model:np.full(shape,np.nan) for model in ['legacy_sweep','strict_sweep']};stop={model:np.zeros(shape,bool) for model in gross};eligible=np.zeros(shape,bool)
        for pid,q in x.groupby('parent_id',sort=False,observed=True):
            i=index[pid];meta=p.loc[pid]
            if family!='4H' or meta.duration==240:
                for t in e.legacy.simulate_parent(q,meta,ors):
                    j=mapping[(t['or_minutes'],t['atr_length'],t['side'])];gross['legacy_sweep'][i,j]=t['gross_points'];stop['legacy_sweep'][i,j]=t['stopped']
            if pid not in ps.index:continue
            meta=ps.loc[pid]
            for j,(opening,n,side) in enumerate(specs):
                trade,ok=e.strict_trade(q,meta,opening,n,side,True);eligible[i,j]=ok
                if trade is not None:gross['strict_sweep'][i,j]=trade[0];stop['strict_sweep'][i,j]=trade[1]
        hashes[family]=e.fingerprints(gross['strict_sweep'],eligible,stop['strict_sweep']);assert hashes[family]==expected[family+'|strict_sweep'],'Strict outcomes differ from previously independently verified full matrix'
        days=np.array(p.session_date,dtype='datetime64[D]').astype('int64');years=pd.DatetimeIndex(np.array(p.session_date,dtype='datetime64[D]')).year.to_numpy();period=e.period(years);slots=p.slot.to_numpy()
        np.savez_compressed(args.private_cache/(family+'.npz'),days=days,slots=slots,period=period,specs=np.array(specs,dtype=str),legacy_gross=gross['legacy_sweep'],strict_gross=gross['strict_sweep'],legacy_stop=stop['legacy_sweep'],strict_stop=stop['strict_sweep'],eligible=eligible)
        for slot in sorted(set(slots)):
            if family=='4H' and slot==5:continue
            clock=(1080+slot*(60 if family=='1H' else 240))%1440 if family in ['1H','4H'] else 1080;label=f'{clock//60:02d}:{clock%60:02d}'
            for j,(opening,n,side) in enumerate(specs):
                for model in gross:
                    for pname in ['development_2016_2022','later_2023_2026']:
                        mask=(slots==slot)&(period==pname);key=f'{family}|{slot}|{opening}|{n}|{side}|{model}|{pname}'
                        rows.append(dict(family=family,slot=int(slot),start_time_ny=label,or_minutes=opening,atr_length=n,side=side,model=model,period=pname,**summarize(gross[model][mask,j],stop[model][mask,j],days[mask],key)))
        print('Finished '+family,flush=True)
    grid=pd.DataFrame(rows);chosen=select(grid);keys=['family','slot','side','model','or_minutes','atr_length'];selected=grid.merge(chosen[keys],on=keys,how='inner',validate='many_to_one');grid.to_csv(args.output/'time-side-grid.csv',index=False,float_format='%.12g');selected.to_csv(args.output/'selected.csv',index=False,float_format='%.12g')
    report={}
    for model,g in selected.groupby('model'):
        dev=g.loc[g.period=='development_2016_2022'].set_index(['family','slot','side']);later=g.loc[g.period=='later_2023_2026'].set_index(['family','slot','side']);report[model]={'selected_groups':len(dev),'positive_development':int((dev.net_avg_points>0).sum()),'positive_later':int((later.net_avg_points>0).sum()),'positive_both':int(((dev.net_avg_points>0)&(later.net_avg_points>0)).sum()),'later_range_above_zero':int((later.net_ci_low>0).sum()),'later_trades':int(later.trades.sum()),'later_trade_weighted_mean':float(later.net_sum_points.sum()/later.trades.sum()),'later_equal_group_mean':float(later.net_avg_points.mean())}
    result={'counts':report,'source_audit':audit,'strict_fingerprint_checks':12,'strict_outcomes_match_previously_independent_replay':True,'selection':C['rule_selection'],'cost_points':C['cost_points'],'resamples':C['bootstrap_repetitions'],'seed':C['seed'],'later_dates_not_untouched':True}
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');assert hashlib.sha256(args.input.read_bytes()).hexdigest()==C['source_sha256'];print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
