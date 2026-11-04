"""Independent fixed-rule recount, including ordered-barrier checks, and small examples."""
import argparse,hashlib,json,math,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import reproduce as subject

def first_touches(close,high,low,indices,h):
    """Direct future-bar matrices, separate from the production extrema/active-path loop."""
    result=np.full(len(close),2,np.int8)
    for a in range(0,len(indices),4096):
        ix=indices[a:a+4096];future=ix[:,None]+np.arange(1,h+1)
        up=high[future]>=close[ix,None]+8;down=low[future]<=close[ix,None]-6.25
        ut=np.where(up.any(axis=1),up.argmax(axis=1),h+1);dt=np.where(down.any(axis=1),down.argmax(axis=1),h+1)
        result[ix]=np.select([ut<dt,dt<ut,(ut==dt)&(ut<=h)],[1,-1,3],default=0)
    return result

class MathematicalChecks(unittest.TestCase):
    def test_sma_direct(self):
        x=np.array([10.,12.,9.,16.,15.]);np.testing.assert_allclose(subject.sma(x,3),[np.nan,np.nan,31/3,37/3,40/3],equal_nan=True)
    def test_weighted_newest(self):
        x=np.array([10.,12.,9.,16.,15.]);wanted=[np.nan,np.nan]+[np.average(x[i-2:i+1],weights=[1,2,3]) for i in range(2,len(x))];np.testing.assert_allclose(subject.wma(x,3),wanted,equal_nan=True)
    def test_ema_seed(self):
        np.testing.assert_allclose(subject.ema(np.array([4.,8.,6.,10.,2.]),3),[np.nan,np.nan,6.,8.,5.],equal_nan=True)
    def test_roll_reset(self):
        np.testing.assert_allclose(subject.segmented(np.arange(8,dtype=float),np.array([0]*4+[1]*4),3,'SMA'),[np.nan,np.nan,1,2,np.nan,np.nan,5,6],equal_nan=True)
    def test_future_high(self):
        np.testing.assert_allclose(subject.extreme(np.array([999.,1,7,3,5]),2,True),[7,7,5,np.nan,np.nan],equal_nan=True)
    def test_future_low(self):
        np.testing.assert_allclose(subject.extreme(np.array([-999.,4,2,8]),2,False),[2,2,np.nan,np.nan],equal_nan=True)
    def test_same_clock_mean(self):
        a=subject.baseline(np.array([.01,.03,-.02]),np.ones(3,bool),np.array([0,0,1]));self.assertAlmostEqual(a[0],.02);self.assertAlmostEqual(a[1],-.02);self.assertTrue(np.isnan(a[2]))
    def test_equal_day_differs_from_minute(self):
        # Invented: one day has 3 signals of +1; another has 1 signal of -2.
        self.assertEqual(np.mean([1,1,1,-2]),.25);self.assertEqual(np.mean([1,-2]),-.5)
    def test_barrier_paths(self):
        c=np.full(5,100.);hi=np.array([100.,109.,100.,109.,100.]);lo=np.array([100.,99.,93.,93.,99.]);out=first_touches(c,hi,lo,np.array([0,1,2]),2);np.testing.assert_array_equal(out[:3],[1,-1,3])
    def test_no_touch(self):
        out=first_touches(np.full(4,100.),np.full(4,101.),np.full(4,99.),np.array([0,1]),2);np.testing.assert_array_equal(out[:2],[0,0])
    def test_strict_rule_equality(self):
        c=np.array([100.,99,98]);a=np.array([100.,100,99]);s=np.array([0.,-1,0]);np.testing.assert_array_equal((c<a)&(s<0),[False,True,False])

def load(source):
    f=pq.read_table(source,columns=['timestamp_utc','high','low','close','roll_transition','is_complete']).to_pandas().sort_values('timestamp_utc',kind='stable');f=f.loc[f.is_complete.fillna(False)].reset_index(drop=True)
    segment=f.roll_transition.fillna(False).cumsum().to_numpy();loc=pd.DatetimeIndex(f.timestamp_utc).tz_convert('America/New_York');minute=((loc.hour.to_numpy()-18)%24)*60+loc.minute.to_numpy();keep=minute<1380;f=f.loc[keep].reset_index(drop=True);segment=segment[keep];minute=minute[keep];loc=loc[keep]
    dates=(loc.normalize()+pd.to_timedelta((loc.hour>=18).astype(int),unit='D')).date;year=np.array([x.year for x in dates]);period=np.select([year<=2014,year<=2022,year<=2024],['HISTORICAL','DISCOVERY','VALIDATION'],default='HOLDOUT');return f,segment,minute,dates,year,period

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);args=p.parse_args();assert hashlib.sha256(args.input.read_bytes()).hexdigest()==subject.CFG['source_sha256']
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MathematicalChecks));assert tests.wasSuccessful()
    f,segment,minute,day,year,period=load(args.input);close=f.close.to_numpy();high=f.high.to_numpy();low=f.low.to_numpy();folder=subject.PACKAGE/'results';fixed=pd.read_csv(folder/'frozen_candidate_results.csv');annual=pd.read_csv(folder/'annual_stability.csv');compared=0;rows=0
    def check(actual,expected,name):
        nonlocal compared
        assert math.isclose(float(actual),float(expected),rel_tol=3e-8,abs_tol=2e-7),(name,actual,expected);compared+=1
    for name in sorted(subject.FIXED_NAMES):
        specs=[(int(h),s) for h,v in subject.FIXED.items() for s in (v['qualified'] or v['top_diagnostics'][:1]) if s['candidate']==name];h,spec=specs[0];n=spec['window'];k=spec['slope_horizon']
        if spec['average_type']=='MOM':signal=np.r_[np.zeros(n,bool),close[n:]<close[:-n]]&np.r_[np.zeros(n,bool),segment[n:]==segment[:-n]]
        else:
            # pandas' rolling grouped mean, independent of cumulative-sum production SMA.
            average=pd.Series(close).groupby(segment,sort=False).transform(lambda x:x.rolling(n,min_periods=n).mean()).to_numpy();lag=np.r_[np.full(k,np.nan),average[:-k]];signal=(close<average)&(average<lag)&np.r_[np.zeros(k,bool),segment[k:]==segment[:-k]]
        future=np.r_[close[h:],np.full(h,np.nan)];valid=np.r_[(segment[h:]==segment[:-h])&(period[h:]==period[:-h]),np.zeros(h,bool)];ret=(future-close)/close;ret[~valid]=np.nan
        maximum=pd.Series(high[::-1]).rolling(h,min_periods=h).max().to_numpy()[::-1];maximum=np.r_[maximum[1:],np.nan];minimum=pd.Series(low[::-1]).rolling(h,min_periods=h).min().to_numpy()[::-1];minimum=np.r_[minimum[1:],np.nan]
        tf=first_touches(close,high,low,np.flatnonzero(signal&valid),h)
        for r in pd.concat([fixed.loc[fixed.candidate==name],annual.loc[annual.candidate==name]],ignore_index=True).itertuples(index=False):
            pname=str(r.period);universe=(year==int(pname))&valid if pname.isdigit() else (period==pname)&valid;chosen=universe&signal;rr=ret[chosen];ix=np.flatnonzero(chosen)
            b=pd.Series(ret[universe]).groupby(minute[universe]).mean();bp=pd.Series((ret[universe]>0).astype(float)).groupby(minute[universe]).mean();bv=b.reindex(minute[chosen]).to_numpy();pv=bp.reindex(minute[chosen]).to_numpy();ex=rr-bv
            daily=pd.Series(ex).groupby(np.asarray(day)[chosen]).mean().to_numpy();seed=int.from_bytes(hashlib.sha256((str(subject.CFG['random_seed'])+'|'+name+'|'+pname+'|'+str(h)).encode()).digest()[:8],'little');rng=np.random.default_rng(seed);resampled=daily[rng.integers(len(daily),size=(subject.CFG['bootstrap_repetitions'],len(daily)))].mean(axis=1)
            fav=np.maximum(maximum[chosen]-close[chosen],0);adv=np.maximum(close[chosen]-minimum[chosen],0)
            expected={'observations':len(ix),'trading_days':len(daily),'years':len(np.unique(year[chosen])),'coverage_pct':100*chosen.sum()/universe.sum(),'positive_pct':100*np.mean(rr>0),'baseline_positive_pct':100*pv.mean(),'excess_positive_pp':100*(np.mean(rr>0)-pv.mean()),'mean_return_pct':100*rr.mean(),'baseline_mean_return_pct':100*bv.mean(),'excess_mean_bp':10000*ex.mean(),'day_balanced_excess_bp':10000*daily.mean(),'day_block_ci_low_bp':10000*np.quantile(resampled,.025),'day_block_ci_high_bp':10000*np.quantile(resampled,.975),'mean_MFE_points':fav.mean(),'mean_MAE_points':adv.mean(),'MFE_MAE_ratio':fav.mean()/adv.mean(),'target_first_pct':100*np.mean(tf[chosen]==1),'stop_first_pct':100*np.mean(tf[chosen]==-1),'no_touch_pct':100*np.mean(tf[chosen]==0),'ambiguous_first_touch_pct':100*np.mean(tf[chosen]==3),'median_return_pct':100*np.median(rr),**{f'p{q}_return_pct':100*np.quantile(rr,q/100) for q in [10,25,75,90]}}
            for field,value in expected.items():check(getattr(r,field),value,(name,pname,field))
            rows+=1
        print('Independent recount passed: '+name,flush=True)
    scan=pd.read_csv(folder/'window_scan.csv');quintiles=pd.read_csv(folder/'signal_quintiles.csv');assert len(scan)==1920 and scan.candidate.nunique()==480 and len(quintiles)==240
    np.testing.assert_allclose(scan[['target_first_pct','stop_first_pct','no_touch_pct','ambiguous_first_touch_pct']].sum(axis=1),100,atol=1e-7)
    result={'passed':True,'invented_mathematical_checks':tests.testsRun,'independent_fixed_and_annual_rows':rows,'independent_metric_comparisons':compared,'candidate_states':480,'full_scan_rows':1920,'quintile_rows':240,'ordered_barriers_independently_recounted':True,'same_input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest()==subject.CFG['source_sha256'],'note':'All four unchanged rules, every period and year independently recounted for 25 metrics, including bootstrap intervals and first-barrier ordering. Full-grid aggregate counts and category partitions also checked. Search rows are overlapping measurements, not independent market samples.'}
    (folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
