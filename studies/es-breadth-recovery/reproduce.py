"""Breadth recovery after weak daily lows; only aggregate outputs are saved."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from breadth_base import FILES,HORIZONS,load as load_base,fingerprint,describe,spaced

HERE=Path(__file__).resolve().parent
CONFIG=json.loads((HERE/'analysis-config.json').read_text())
GROUPS=['poor','middle','partial','strong']

def group_values(recovery):
    return pd.Series(np.select([recovery.le(.25),recovery.lt(.40),recovery.lt(.75),recovery.le(1)],GROUPS,default='undefined'),index=recovery.index)

def load(folder):
    f,checks=load_base(folder);quality={}
    for series in ['b200','b50']:
        g=pd.read_csv(folder/FILES[series]).set_index('time').reindex(f.index)
        valid=np.isfinite(g[['open','high','low','close']]).all(axis=1)&g[['open','high','low','close']].ge(0).all(axis=1)&g[['open','high','low','close']].le(100).all(axis=1)&g.low.le(g[['open','close','high']].min(axis=1))&g.high.ge(g[['open','close','low']].max(axis=1))
        # Fail rather than silently discard corrupt candles or clip invalid recovery.
        assert valid.all(),f'{series}: invalid OHLC records'
        width=g.high-g.low;rec=(g.close-g.low)/width.where(width.gt(0))
        f[series+'_low']=g.low;f[series+'_recovery']=rec;f[series+'_group']=group_values(rec)
        quality[series]={'common_rows':len(g),'zero_range_days':int(width.eq(0).sum()),'valid_nonzero_range_days':int(width.gt(0).sum()),'invalid_OHLC_days':int((~valid).sum())}
    checks['breadth_daily_OHLC']=quality
    return f,checks

def first_per_spell(frame):
    return frame.loc[~frame.spell.duplicated()]

def calculate(f):
    results={};rows=[]
    for label,(series,threshold) in CONFIG['washouts'].items():
        signal=f[series+'_low'].le(threshold)
        starts=signal&~signal.shift(1,fill_value=False)
        g=f.loc[signal].copy();g['spell']=starts.cumsum().loc[signal]
        detail={'low_breadth_days':len(g),'low_breadth_spells':int(starts.sum()),'undefined_recovery_days':int(g[series+'_recovery'].isna().sum()),'groups':{},'all_washout_days':{str(h):describe(g,h) for h in HORIZONS}}
        for group in GROUPS:
            selected=g.loc[g[series+'_group'].eq(group)]
            d={'signal_days':len(selected),'spells_with_this_group':int(selected.spell.nunique()),'horizons':{}}
            for h in HORIZONS:
                available=selected.loc[selected[f'r{h}'].notna()]
                methods={'all_signal_days':available,'first_per_washout_spell':first_per_spell(available),'nonoverlapping':spaced(available,h),'five_session_spacing':spaced(available,5)}
                d['horizons'][str(h)]={method:describe(frame,h) for method,frame in methods.items()}
                for method,values in d['horizons'][str(h)].items():rows.append({'washout':label,'recovery_group':group,'forward_ES_sessions':h,'counting_method':method,**values})
            detail['groups'][group]=d
        results[label]=detail
    return results,pd.DataFrame(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--output',type=Path,default=HERE/'results');a=p.parse_args()
    before={k:fingerprint(a.input_dir/v) for k,v in FILES.items()};f,checks=load(a.input_dir);results,table=calculate(f)
    periods={}
    for label,(series,threshold) in CONFIG['washouts'].items():
        periods[label]={}
        for period,mask in [('2017_2021',f.index<'2022-01-01'),('2022_2026',f.index>='2022-01-01')]:
            periods[label][period]={group:{str(h):describe(f.loc[mask&f[series+'_low'].le(threshold)&f[series+'_group'].eq(group)],h) for h in HORIZONS} for group in GROUPS}
    out={'checked_date':'2026-10-16','question':'After a weak daily breadth low, did partial recovery precede stronger ES chart-price changes than strong recovery?','config':CONFIG,'source_sha256':before,'checks':checks,'baseline':{str(h):describe(f,h) for h in HORIZONS},'results':results,'periods':periods,'aggregate_rows':len(table)}
    assert before=={k:fingerprint(a.input_dir/v) for k,v in FILES.items()}
    a.output.mkdir(parents=True,exist_ok=True);(a.output/'summary.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');table.to_csv(a.output/'recovery_summary.csv',index=False)
    print(json.dumps({'quality':checks['breadth_daily_OHLC'],'primary':results['200_low40'],'aggregate_rows':len(table)},indent=2))

if __name__=='__main__':main()
