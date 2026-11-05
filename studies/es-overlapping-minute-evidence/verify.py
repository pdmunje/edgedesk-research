"""Independent pandas/grouped recount and small mathematical examples."""
import argparse,hashlib,json,math,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import reproduce as s

class Examples(unittest.TestCase):
    def test_weight_reversal(self):
        n=np.array([3,1]);a=np.array([1.,-2]);self.assertEqual(np.average(a,weights=n),.25);self.assertEqual(a.mean(),-.5)
    def test_covariance_identity(self):
        n=np.array([3,1]);a=np.array([1.,-2]);self.assertAlmostEqual(np.mean((n-n.mean())*(a-a.mean()))/n.mean(),np.average(a,weights=n)-a.mean())
    def test_equal_counts(self):
        a=np.array([4.,-3,2]);self.assertEqual(np.average(a,weights=[2,2,2]),a.mean())
    def test_overlap_increments(self):
        self.assertEqual(len(set(range(1,61))&set(range(2,62))),59);self.assertEqual(len(set(range(1,241))&set(range(2,242))),239)
    def test_disjoint_geometry(self):
        self.assertEqual(s.greedy_count(np.array([0,1,60,61]),np.zeros(100,int),60),2)
    def test_roll_resets_disjoint_geometry(self):
        self.assertEqual(s.greedy_count(np.array([0,2]),np.array([0,0,1]),60),2)
    def test_averages(self):
        for kind in ['SMA','WMA']:
            x=np.array([1.,2,4,3,9]);wanted=[np.nan,np.nan]+[np.mean(x[i-2:i+1]) if kind=='SMA' else np.average(x[i-2:i+1],weights=[1,2,3]) for i in range(2,5)];np.testing.assert_allclose(s.average(x,np.zeros(5),3,kind),wanted,equal_nan=True)
    def test_feature_roll_reset(self):
        out=s.average(np.arange(8.),np.array([0]*4+[1]*4),3,'SMA');self.assertTrue(np.isnan(out[4:6]).all());self.assertEqual(out[6],5)
    def test_slot_denominator(self):
        v=s.mean_by_slot(np.array([1.,3,99]),np.array([True,True,False]),np.array([0,0,1]));self.assertEqual(v[0],2);self.assertTrue(np.isnan(v[1]))

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);args=p.parse_args();assert hashlib.sha256(args.input.read_bytes()).hexdigest()==s.CFG['source_sha256'];tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Examples));assert tests.wasSuccessful()
    f=pq.read_table(args.input,columns=['timestamp_utc','close','roll_transition','is_complete']).to_pandas().sort_values('timestamp_utc',kind='stable');f=f.loc[f.is_complete.fillna(False)].reset_index(drop=True);seg=f.roll_transition.fillna(False).cumsum().to_numpy();loc=pd.DatetimeIndex(f.timestamp_utc).tz_convert('America/New_York');slots=((loc.hour.to_numpy()-18)%24)*60+loc.minute.to_numpy();keep=slots<1380;f=f.loc[keep].reset_index(drop=True);seg=seg[keep];slots=slots[keep];loc=loc[keep];dates=(loc.normalize()+pd.to_timedelta((loc.hour>=18).astype(int),unit='D')).date;year=np.array([d.year for d in dates]);period=np.select([year<=2014,year<=2022,year<=2024],['HISTORICAL','DISCOVERY','VALIDATION'],default='LATER');close=f.close.to_numpy();saved=pd.read_csv(s.PACKAGE/'results/weighting-and-overlap.csv');compared=0
    for spec in s.CFG['cases']:
        n=spec['length'];k=spec['slope_bars'];h=spec['horizon'];ma=np.full(len(close),np.nan)
        for indices in pd.Series(np.arange(len(close))).groupby(seg,sort=False):
            ix=indices[1].to_numpy();x=close[ix]
            if len(x)<n:continue
            if spec['average']=='SMA':ma[ix]=pd.Series(x).rolling(n).mean().to_numpy()
            else:
                total=x[:n].sum();w=np.dot(x[:n],np.arange(1,n+1));den=n*(n+1)/2;ma[ix[n-1]]=w/den
                for j in range(n,len(x)):w+=n*x[j]-total;total+=x[j]-x[j-n];ma[ix[j]]=w/den
        past=np.r_[np.full(k,np.nan),ma[:-k]];signal=(close<ma)&(ma<past)&np.r_[np.zeros(k,bool),seg[k:]==seg[:-k]];future=np.r_[close[h:],np.full(h,np.nan)];valid=np.r_[(seg[h:]==seg[:-h])&(period[h:]==period[:-h]),np.zeros(h,bool)];ret=spec['direction']*(future/close-1)*10000
        for pname in ['HISTORICAL','DISCOVERY','VALIDATION','LATER']:
            universe=valid&(period==pname);chosen=universe&signal;ix=np.flatnonzero(chosen);reference=pd.Series(ret[universe]).groupby(slots[universe]).mean();ex=ret[chosen]-reference.reindex(slots[chosen]).to_numpy();daily=pd.DataFrame({'day':dates[chosen],'extra':ex}).groupby('day').extra.agg(['count','mean']);count=daily['count'].to_numpy();effect=daily['mean'].to_numpy();weighted=np.average(effect,weights=count);equal=effect.mean();cov=np.cov(count,effect,ddof=0)[0,1];seed=int.from_bytes(hashlib.sha256((str(s.CFG['random_seed'])+'|'+spec['id']+'|'+pname).encode()).digest()[:8],'little');rng=np.random.default_rng(seed);sample=rng.integers(len(count),size=(s.CFG['bootstrap_repetitions'],len(count)));ww=(count[sample]*effect[sample]).sum(axis=1)/count[sample].sum(axis=1);ee=effect[sample].mean(axis=1);bounds=np.quantile(ww,[.025,.975]);dbounds=np.quantile(ee,[.025,.975]);top=max(1,math.ceil(len(count)/10));pairs=sum(int(seg[b]==seg[a] and b-a<h) for a,b in zip(ix[:-1],ix[1:]));ends={};disjoint=0
            for i in ix:
                contract=seg[i]
                if i>=ends.get(contract,-1):disjoint+=1;ends[contract]=i+h
            expected={'horizon':h,'observations':len(ix),'signal_days':len(count),'mean_signals_per_day':count.mean(),'median_signals_per_day':np.median(count),'minimum_signals_per_day':count.min(),'maximum_signals_per_day':count.max(),'top_tenth_days_count':top,'top_tenth_days_signal_share_pct':100*np.sort(count)[-top:].sum()/count.sum(),'equal_minute_extra_bp':weighted,'equal_day_extra_bp':equal,'weighting_gap_bp':weighted-equal,'count_effect_covariance':cov,'covariance_divided_mean_count_bp':cov/count.mean(),'minute_day_block_low_bp':bounds[0],'minute_day_block_high_bp':bounds[1],'equal_day_block_low_bp':dbounds[0],'equal_day_block_high_bp':dbounds[1],'successive_signal_pairs':len(ix)-1,'overlapping_successive_pairs':pairs,'overlapping_successive_pairs_pct':100*pairs/(len(ix)-1),'greedy_nonoverlapping_windows':disjoint};row=saved.loc[(saved['case']==spec['id'])&(saved.period==pname)].iloc[0]
            for field,v in expected.items():assert math.isclose(float(row[field]),float(v),rel_tol=2e-8,abs_tol=2e-7),(spec['id'],pname,field,row[field],v);compared+=1
            assert math.isclose(weighted-equal,cov/count.mean(),abs_tol=1e-10)
        print('Independent recount passed: '+spec['id'],flush=True)
    result={'passed':True,'mathematical_examples':tests.testsRun,'independent_rows':len(saved),'independent_metric_comparisons':compared,'same_source_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest()==s.CFG['source_sha256'],'note':'Independent features, clock references, day groups, weighting/covariance identity, both day-block intervals, overlap counts and greedy disjoint-window geometry. No effective-independent-sample-size claim.'};(s.PACKAGE/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
