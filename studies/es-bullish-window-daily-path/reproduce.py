"""Day counts and sizes inside previously explored ES research windows."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'analysis-config.json').read_text())
FILES={'es':'CME_MINI_ES1!, 1D_c578e.csv','b200':'INDEX_S5TH, D_0f94a.csv','b50':'INDEX_S5FI, D_96a6d.csv','b20':'INDEX_S5TW, D_dc629.csv','b5':'INDEX_S5FD, D_905a5.csv','skew':'CBOE_DLY_SKEW, 1W_a7232.csv'}
def fingerprint(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def standardized(s):
    past=s.shift(1);sd=past.rolling(104,min_periods=104).std(ddof=1)
    return (s-past.rolling(104,min_periods=104).mean())/sd.where(sd.gt(0))
def spaced(entries,h):
    kept=[]
    for entry in entries:
        if not kept or entry>=kept[-1]+h:kept.append(int(entry))
    return kept
def prepare(folder):
    raw={};checks={}
    for name,file in FILES.items():
        g=pd.read_csv(folder/file).set_index('time');dates=pd.to_datetime(g.index)
        assert dates.is_unique and dates.is_monotonic_increasing
        assert np.isfinite(g[['open','high','low','close']]).all().all()
        assert g.low.le(g[['open','close']].min(axis=1)).all() and g.high.ge(g[['open','close']].max(axis=1)).all()
        if name.startswith('b'):assert g[['open','high','low','close']].ge(0).all().all() and g[['open','high','low','close']].le(100).all().all()
        else:assert g[['open','high','low','close']].gt(0).all().all()
        raw[name]=g;checks[name]={'rows':len(g),'first_source_date':g.index.min(),'last_source_date':g.index.max()}
    es=raw['es'].loc[:CONFIG['last_complete_ES_date']].copy();es['row']=np.arange(len(es));dates=pd.to_datetime(es.index);es['year']=dates.year;es['weekday']=dates.weekday
    es['cc']=100*(es.close/es.close.shift(1)-1);es['oc']=100*(es.close/es.open-1);es['gap']=100*(es.open/es.close.shift(1)-1);es['range']=100*(es.high-es.low)/es.open
    common=set(es.index)
    for name in ['b200','b50','b20','b5']:common&=set(raw[name].index)
    common=sorted(common);signals={};zero={}
    for name,label,cutoff in [('b200','breadth200_partial',40),('b50','breadth50_partial',30)]:
        g=raw[name].loc[common];width=g.high-g.low;recovery=(g.close-g.low)/width.where(width.gt(0));mask=g.low.le(cutoff)&recovery.ge(.4)&recovery.lt(.75)
        signals[label]=[int(es.loc[d,'row'])+1 for d in g.index[mask]];zero[name]=int(width.eq(0).sum())
    sk=raw['skew'].copy();sk.index=pd.to_datetime(sk.index);weeks=sk.index-pd.to_timedelta(sk.index.dayofweek,unit='D');assert weeks.is_unique;remapped=int((sk.index!=weeks).sum());sk.index=weeks;sk=sk.loc[:CONFIG['last_complete_SKEW_week_start']]
    grid=sk.reindex(pd.date_range(sk.index.min(),CONFIG['last_complete_SKEW_week_start'],freq='W-MON'));change=grid.close-grid.open;z=standardized(change);zr=standardized(sk.close-sk.open)
    esweeks=dates-pd.to_timedelta(dates.weekday,unit='D')
    for name,mask in [('skew_drop5',change.le(-5)),('skew_normalized_calendar',z.le(-1.5)),('skew_normalized_reported',zr.le(-1.5))]:
        signals[name]=[]
        for w in mask.index[mask]:
            positions=np.flatnonzero(esweeks==w+pd.Timedelta(weeks=1))
            if len(positions):signals[name].append(int(positions[0]))
    checks.update(complete_ES_rows=len(es),excluded_ES_developing_rows=len(raw['es'])-len(es),breadth_common_dates=len(common),breadth_common_first=common[0],breadth_common_last=common[-1],breadth_zero_range_days=zero,holiday_SKEW_labels_remapped=remapped,excluded_SKEW_developing_rows=len(raw['skew'])-len(sk),missing_SKEW_weeks=[str(d.date()) for d in grid.index[grid.close.isna()]],signal_entries_before_forward_exclusion={k:len(v) for k,v in signals.items()})
    return es,signals,checks
def measure(values,weights):
    x=np.asarray(values,dtype=float);w=np.asarray(weights,dtype=float);assert len(x)==len(w) and np.isfinite(x).all() and (w>0).all();total=float(w.sum());positive=x>0;negative=x<0;zero=x==0
    return {'day_weight':total,'positive_day_weight':float(w[positive].sum()),'negative_day_weight':float(w[negative].sum()),'zero_day_weight':float(w[zero].sum()),'positive_pct':float(100*w[positive].sum()/total),'negative_pct':float(100*w[negative].sum()/total),'zero_pct':float(100*w[zero].sum()/total),'mean_pct':float(np.dot(x,w)/total),'mean_positive_pct':float(np.dot(x[positive],w[positive])/w[positive].sum()) if positive.any() else None,'mean_negative_pct':float(np.dot(x[negative],w[negative])/w[negative].sum()) if negative.any() else None}
def references(es,entry,h):
    positions=es.row.to_numpy();years=es.year.to_numpy();weekdays=es.weekday.to_numpy()
    valid=(positions>=1)&(positions+h<=len(es))&(years==years[entry])&(weekdays==weekdays[entry])&((positions+h<=entry)|(positions>=entry+h))
    candidates=positions[valid].tolist()
    return spaced(candidates,h)
def describe(es,entries,h):
    refs={i:references(es,i,h) for i in entries};matched=[i for i in entries if refs[i]];assert matched
    # No held day repeats among main entries; reference days may recur across different event comparisons.
    actual=np.concatenate([np.arange(i,i+h) for i in matched]);rw=[];ri=[]
    for i in matched:
        for j in refs[i]:ri.extend(range(j,j+h));rw.extend([1/len(refs[i])]*h)
    ri=np.array(ri,dtype=int);rw=np.array(rw);actual_weight=np.ones(len(actual));out={'events':len(entries),'matched_events':len(matched),'unmatched_events':len(entries)-len(matched),'event_days':len(actual),'unique_event_days':len(set(actual.tolist())),'first_entry_date':es.index[min(matched)],'last_entry_date':es.index[max(matched)],'last_outcome_date':es.index[max(matched)+h-1],'minimum_reference_windows':min(len(refs[i]) for i in matched),'median_reference_windows':float(np.median([len(refs[i]) for i in matched])),'reference_window_appearances':sum(len(refs[i]) for i in matched),'reference_day_appearances':len(ri),'unique_reference_days':len(set(ri.tolist()))}
    out['measures']={name:{'signal':measure(es[key].iloc[actual].to_numpy(),actual_weight),'reference':measure(es[key].iloc[ri].to_numpy(),rw)} for name,key in [('close_to_close','cc'),('open_to_close','oc'),('prior_close_to_open','gap')]}
    returns=100*(es.close.iloc[[i+h-1 for i in matched]].to_numpy()/es.open.iloc[matched].to_numpy()-1)
    ref_return=[]
    for i in matched:ref_return.append(np.mean([100*(es.close.iloc[j+h-1]/es.open.iloc[j]-1) for j in refs[i]]))
    out.update(mean_range_pct=float(es['range'].iloc[actual].mean()),reference_mean_range_pct=float(np.average(es['range'].iloc[ri],weights=rw)),mean_window_change_pct=float(returns.mean()),positive_windows=int((returns>0).sum()),positive_windows_pct=float(100*(returns>0).mean()),reference_mean_window_change_pct=float(np.mean(ref_return)))
    path=[]
    for d in range(1,h+1):
        positions=[i+d-1 for i in matched];cum=[100*(es.close.iloc[i+d-1]/es.open.iloc[i]-1) for i in matched];rr=[];ref_oc=[];ref_cc=[]
        for i in matched:
            rr.append(np.mean([100*(es.close.iloc[j+d-1]/es.open.iloc[j]-1) for j in refs[i]]));ref_oc.append(np.mean([es.oc.iloc[j+d-1] for j in refs[i]]));ref_cc.append(np.mean([es.cc.iloc[j+d-1]>0 for j in refs[i]]))
        path.append({'session_number':d,'windows':len(matched),'mean_cumulative_pct':float(np.mean(cum)),'reference_mean_cumulative_pct':float(np.mean(rr)),'mean_session_open_to_close_pct':float(es.oc.iloc[positions].mean()),'positive_close_to_close_days':int(es.cc.iloc[positions].gt(0).sum()),'positive_close_to_close_pct':float(100*es.cc.iloc[positions].gt(0).mean()),'reference_positive_close_to_close_pct':float(100*np.mean(ref_cc)),'reference_mean_session_open_to_close_pct':float(np.mean(ref_oc))})
    return out,path
def calculate(es,signals):
    results={};rows=[];pathrows=[]
    for condition,entries in signals.items():
        h=CONFIG['conditions'][condition]['horizon_observed_ES_sessions'];valid=sorted(set(i for i in entries if i>=1 and i+h<=len(es)));results[condition]={'horizon_sessions':h,'complete_signal_windows':len(valid),'methods':{}}
        for method,chosen in [('nonoverlapping_primary',spaced(valid,h)),('all_signals_audit',valid)]:
            d,p=describe(es,chosen,h);results[condition]['methods'][method]={'summary':d,'daily_path':p}
            for metric,values in d['measures'].items():rows.append({'condition':condition,'counting_method':method,'horizon_sessions':h,'measure':metric,'matched_windows':d['matched_events'],'event_days':d['event_days'],**{'signal_'+k:v for k,v in values['signal'].items()},**{'reference_'+k:v for k,v in values['reference'].items()}})
            for day in p:pathrows.append({'condition':condition,'counting_method':method,**day})
    return results,pd.DataFrame(rows),pd.DataFrame(pathrows)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,required=True);a=p.parse_args();before={k:fingerprint(a.input_dir/v) for k,v in FILES.items()};es,signals,checks=prepare(a.input_dir);results,table,paths=calculate(es,signals);assert before=={k:fingerprint(a.input_dir/v) for k,v in FILES.items()}
    out={'checked_date':'2026-10-16','config':CONFIG,'source_sha256':before,'checks':checks,'results':results,'distribution_rows':len(table),'path_rows':len(paths)};folder=HERE/'results';folder.mkdir(exist_ok=True);(folder/'summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8');table.to_csv(folder/'distribution_summary.csv',index=False);paths.to_csv(folder/'path_summary.csv',index=False)
    print(json.dumps({'checks':checks,'primary':{k:v['methods']['nonoverlapping_primary']['summary'] for k,v in results.items()}},indent=2))
if __name__=='__main__':main()
