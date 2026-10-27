"""Recount aggregates and selection from temporary outcomes; check saved source replay."""
import argparse,json,math,unittest,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import reproduce as r

class SelectionChecks(unittest.TestCase):
    def frame(self,rows):
        return pd.DataFrame([dict(model='strict_sweep',family='1H',slot=0,side='long',period='development_2016_2022',or_minutes=o,atr_length=a,trades=n,net_avg_points=m) for o,a,n,m in rows])
    def test_minimum_100(self):
        self.assertEqual(r.select(self.frame([(1,9,99,100),(2,14,100,1)])).iloc[0].or_minutes,2)
    def test_later_never_selects(self):
        d=self.frame([(1,9,100,1),(2,14,100,10)]);d.loc[1,'period']='later_2023_2026';self.assertEqual(r.select(d).iloc[0].or_minutes,1)
    def test_tie_prefers_count(self):
        self.assertEqual(r.select(self.frame([(1,9,100,1),(2,14,101,1)])).iloc[0].or_minutes,2)
    def test_full_tie_prefers_short_range_then_atr(self):
        row=r.select(self.frame([(5,9,100,1),(1,14,100,1),(1,9,100,1)])).iloc[0];self.assertEqual((row.or_minutes,row.atr_length),(1,9))
    def test_no_eligible_candidate(self):self.assertEqual(len(r.select(self.frame([(1,9,99,1)]))),0)
    def test_zero_and_negative_are_retained(self):self.assertEqual(r.select(self.frame([(1,9,100,-1),(2,9,100,-2)])).iloc[0].net_avg_points,-1)

def main():
    a=argparse.ArgumentParser();a.add_argument('--private-cache',required=True,type=Path);args=a.parse_args();suite=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SelectionChecks));assert suite.wasSuccessful()
    grid=pd.read_csv(r.P/'results/time-side-grid.csv');selected=pd.read_csv(r.P/'results/selected.csv');checks=0
    def eq(a,b):
        nonlocal checks
        assert (pd.isna(a) and pd.isna(b)) or math.isclose(float(a),float(b),abs_tol=3e-7,rel_tol=3e-9),(a,b);checks+=1
    interval_rows=0
    for family,g in grid.groupby('family'):
        with np.load(args.private_cache/(family+'.npz'),allow_pickle=False) as archive:z={key:archive[key] for key in archive.files}
        specs=[tuple(x) for x in z['specs']]
        for row in g.itertuples(index=False):
            j=specs.index((str(row.or_minutes),str(row.atr_length),row.side));mask=(z['slots']==row.slot)&(z['period']==row.period);values=z['legacy_gross' if row.model=='legacy_sweep' else 'strict_gross'][mask,j];stops=z['legacy_stop' if row.model=='legacy_sweep' else 'strict_stop'][mask,j];good=np.isfinite(values);v=values[good];net=[float(x)-.59 for x in v];days=z['days'][mask][good]
            expected={'trades':len(net),'signal_days':len(set(days)),'gross_avg_points':sum(map(float,v))/len(v) if len(v) else np.nan,'net_sum_points':sum(net),'net_avg_points':sum(net)/len(net) if net else np.nan,'net_positive_trades':sum(x>0 for x in net),'stopped_trades':sum(stops[good])}
            for k,v in expected.items():eq(getattr(row,k),v)
            if len(net) and len(selected.loc[(selected.model==row.model)&(selected.family==family)&(selected.slot==row.slot)&(selected.side==row.side)&(selected.or_minutes==row.or_minutes)&(selected.atr_length==row.atr_length)]):
                assert len(set(days))==len(net),'Expected one trade per group/session'
                key=f'{family}|{row.slot}|{row.or_minutes}|{row.atr_length}|{row.side}|{row.model}|{row.period}'
                seed=int.from_bytes(hashlib.sha256((str(r.C['seed'])+'|'+key).encode()).digest()[:8],'little')
                samples=np.random.default_rng(seed).integers(0,len(net),size=(r.C['bootstrap_repetitions'],len(net)))
                values=np.array([v for _,v in sorted(zip(days,net))]);lo,hi=np.quantile(values[samples].mean(axis=1),[.025,.975]);eq(row.net_ci_low,lo);eq(row.net_ci_high,hi);interval_rows+=1
    keys=['model','family','slot','side'];chosen=[]
    for key,g in grid.loc[grid.period=='development_2016_2022'].groupby(keys):
        candidates=[x for x in g.to_dict('records') if x['trades']>=100 and math.isfinite(x['net_avg_points'])]
        if not candidates:continue
        winner=min(candidates,key=lambda x:(-x['net_avg_points'],-x['trades'],x['or_minutes'],x['atr_length']));chosen.append(tuple(winner[k] for k in keys+['or_minutes','atr_length']))
    actual=set(tuple(x) for x in selected[keys+['or_minutes','atr_length']].itertuples(index=False,name=None));assert actual==set(chosen);assert len(selected)==2*len(chosen)
    baseline=pd.read_csv(r.P/'source-selection-summary.csv');sourcechecks=0
    for old in baseline.itertuples(index=False):
        period='later_2023_2026' if old.period=='holdout_2023_2026' else old.period
        new=selected.loc[(selected.model=='legacy_sweep')&(selected.family==old.family)&(selected.slot==old.slot)&(selected.side==old.side)&(selected.period==period)]
        assert len(new)==1,(old.family,old.slot,old.side,period)
        row=new.iloc[0]
        for a,b in [(row.or_minutes,old.selected_or_minutes),(row.atr_length,old.selected_atr_length),(row.trades,old.trades),(row.gross_avg_points,old.gross_avg),(row.net_avg_points,old.net_avg)]:eq(a,b);sourcechecks+=1
    result={'passed':True,'selection_fixtures':suite.testsRun,'grid_rows_recounted':len(grid),'selected_rows':len(selected),'selection_groups_bruteforce':len(chosen),'numeric_checks':checks,'selected_interval_rows_recounted':interval_rows,'original_saved_selection_checks':sourcechecks,'limits':'Aggregate recount uses temporary replay outcomes, not a second independent vendor-bar implementation. Strict full-matrix hashes separately match the earlier independent replay. Selected intervals independently recounted using one trade per group/session; other candidate intervals not separately checked.'}
    (r.P/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
