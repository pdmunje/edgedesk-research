"""Breadth at ES closing highs; aggregate research outputs, no source bars."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from breadth_base import FILES,HORIZONS,LAST_COMPLETE,load as load_base,describe,spaced,fingerprint
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'analysis-config.json').read_text())
LOOKBACKS=CONFIG['lookbacks_observations_including_today']

def high_flag(close,lookback):
    maximum=close.rolling(lookback,min_periods=lookback).max()
    return close.ge(maximum).where(maximum.notna()).astype('boolean')

def load(folder):
    f,checks=load_base(folder)
    es=pd.read_csv(folder/FILES['es']).set_index('time').loc[:LAST_COMPLETE]
    f['breadth_mean']=f[['b5','b20','b50','b200']].mean(axis=1)
    sources={name:pd.read_csv(folder/FILES[name]).set_index('time').close for name in ['b5','b20','b50','b200']}
    for L in LOOKBACKS:
        f[f'es_high{L}']=high_flag(es.close,L).reindex(f.index).fillna(False)
        flags={};recent={}
        for name,close in sources.items():
            flag=high_flag(close,L);recent_flag=flag.astype(float).rolling(5,min_periods=5).max()
            flags[name]=flag.reindex(f.index);recent[name]=recent_flag.reindex(f.index)
        same=pd.DataFrame(flags);last5=pd.DataFrame(recent)
        f[f'confirmation_valid{L}']=same.notna().all(axis=1)
        f[f'confirmed_count{L}']=same.sum(axis=1).where(f[f'confirmation_valid{L}'])
        f[f'recent_valid{L}']=last5.notna().all(axis=1)
        f[f'recent_count{L}']=last5.sum(axis=1).where(f[f'recent_valid{L}'])
        for name in sources:f[f'recent_{name}_{L}']=last5[name]
    prior=es.close.shift(1).rolling(20,min_periods=20).max()
    f['strict_prior20_high']=es.close.gt(prior).reindex(f.index).fillna(False)
    return f,checks

def signals(f):
    out={}
    for L in LOOKBACKS:
        high=f[f'es_high{L}'].astype(bool);valid=f[f'confirmation_valid{L}'];count=f[f'confirmed_count{L}']
        out[f'L{L}_all_highs']=high
        out[f'L{L}_mean_below50']=high&f.breadth_mean.lt(50)
        out[f'L{L}_mean_50to80']=high&f.breadth_mean.ge(50)&f.breadth_mean.lt(80)
        out[f'L{L}_mean_atleast80']=high&f.breadth_mean.ge(80)
        out[f'L{L}_no_confirmation']=high&valid&count.eq(0)
        out[f'L{L}_some_confirmation']=high&valid&count.gt(0)
        out[f'L{L}_confirmation_eligible']=high&valid
    return out

def calculate(f):
    result={};rows=[]
    for name,signal in signals(f).items():
        all_days=f.loc[signal];first=f.loc[signal&~signal.shift(1,fill_value=False)]
        detail={'signal_dates':len(all_days),'consecutive_signal_runs':len(first),'horizons':{}}
        for h in HORIZONS:
            available=all_days.loc[all_days[f'r{h}'].notna()]
            frames={'all_signal_days':available,'first_consecutive_signal_day':first,'nonoverlapping':spaced(available,h),'five_session_spacing':spaced(available,5)}
            detail['horizons'][str(h)]={key:describe(g,h) for key,g in frames.items()}
            for key,values in detail['horizons'][str(h)].items():rows.append({'condition':name,'forward_ES_sessions':h,'counting_method':key,**values})
        result[name]=detail
    return result,pd.DataFrame(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,required=True);a=p.parse_args()
    before={k:fingerprint(a.input_dir/v) for k,v in FILES.items()};f,checks=load(a.input_dir);results,table=calculate(f)
    confirmations={}
    for L in LOOKBACKS:
        high=f[f'es_high{L}'];same=f.loc[high&f[f'confirmation_valid{L}']];recent=f.loc[high&f[f'recent_valid{L}']]
        confirmations[str(L)]={'ES_high_dates':int(high.sum()),'same_day_eligible_highs':len(same),'same_day_ineligible_highs':int(high.sum())-len(same),'median_series_confirming_same_day':float(same[f'confirmed_count{L}'].median()),'same_day_zero_confirmation':int(same[f'confirmed_count{L}'].eq(0).sum()),'recent_five_eligible_highs':len(recent),'recent_five_ineligible_highs':int(high.sum())-len(recent),'recent_five_series':{name:{'confirmed_dates':int(recent[f'recent_{name}_{L}'].sum()),'denominator':len(recent),'confirmed_pct':float(100*recent[f'recent_{name}_{L}'].mean())} for name in ['b5','b20','b50','b200']}}
    primary=signals(f)['L20_mean_atleast80']
    periods={period:{group:{str(h):describe(f.loc[mask&signal],h) for h in HORIZONS} for group,signal in [('primary',primary),('all_20_highs',f.es_high20)]} for period,mask in [('2017_2021',f.index<'2022-01-01'),('2022_2026',f.index>='2022-01-01')]}
    audit={'inclusive_current20':{str(h):describe(f.loc[primary],h) for h in HORIZONS},'strict_above_previous20':{str(h):describe(f.loc[f.strict_prior20_high&f.breadth_mean.ge(80)],h) for h in HORIZONS}}
    out={'checked_date':'2026-10-16','config':CONFIG,'source_sha256':before,'checks':checks,'baseline':{str(h):describe(f,h) for h in HORIZONS},'results':results,'confirmation_frequency':confirmations,'primary_periods':periods,'high_definition_audit':audit,'aggregate_rows':len(table)}
    assert before=={k:fingerprint(a.input_dir/v) for k,v in FILES.items()}
    output=HERE/'results';output.mkdir(exist_ok=True);(output/'summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8');table.to_csv(output/'highs_summary.csv',index=False)
    print(json.dumps({'primary':{h:{m:{k:r[k] for k in ['events','mean_pct','positive_events']} for m,r in methods.items()} for h,methods in results['L20_mean_atleast80']['horizons'].items()},'confirmation':confirmations,'definition_audit':audit,'aggregate_rows':len(table)},indent=2))
if __name__=='__main__':main()
