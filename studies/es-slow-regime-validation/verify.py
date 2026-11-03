"""Independent fixed-rule recount plus tests against direct mathematical calculations."""
import argparse,hashlib,json,math,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import reproduce as subject

def direct_ma(x,segments,n,kind):
    out=np.full(len(x),np.nan);starts=np.r_[0,np.flatnonzero(np.diff(segments))+1];ends=np.r_[starts[1:],len(x)]
    for a,b in zip(starts,ends):
        z=x[a:b]
        if len(z)<n:continue
        if kind=='SMA':out[a:b]=pd.Series(z).rolling(n,min_periods=n).mean().to_numpy()
        elif kind=='WMA':
            total=float(np.sum(z[:n]));weighted=float(np.dot(z[:n],np.arange(1,n+1)));den=n*(n+1)/2;out[a+n-1]=weighted/den
            for j in range(n,len(z)):
                weighted+=n*z[j]-total;total+=z[j]-z[j-n];out[a+j]=weighted/den
        else:raise ValueError(kind)
    return out

class MathematicalChecks(unittest.TestCase):
    def test_sma_wma_against_direct_windows(self):
        x=np.array([10,11,9,14,12,18,16.]);segments=np.zeros(len(x),int)
        for kind in ['SMA','WMA']:
            calculated=subject.reset_by_segment(x,segments,3,kind)
            expected=np.array([np.nan,np.nan]+[np.mean(x[i-2:i+1]) if kind=='SMA' else np.average(x[i-2:i+1],weights=[1,2,3]) for i in range(2,len(x))]);np.testing.assert_allclose(calculated,expected,equal_nan=True)
    def test_roll_restarts_warmup(self):
        actual=subject.reset_by_segment(np.arange(8,dtype=float),np.array([0]*4+[1]*4),3,'SMA');self.assertTrue(np.isnan(actual[4:6]).all());self.assertEqual(actual[6],5)
    def test_ema_seed_and_warmup(self):
        x=np.array([4.,8.,6.,10.,2.]);expected=[];value=x[0]
        for i,p in enumerate(x):
            if i:value=.5*p+.5*value
            expected.append(value if i>=2 else np.nan)
        np.testing.assert_allclose(subject.rolling_ema(x,3),expected,equal_nan=True)
    def test_regression_matches_independent_least_squares(self):
        y=100+2*np.arange(8)+np.array([0,.2,-.1,.3,0,-.2,.1,-.1]);values=subject.rolling_regression(y,np.zeros(8,int),5)
        for i in range(4,len(y)):
            x=np.arange(5);intercept,slope=np.linalg.lstsq(np.column_stack([np.ones(5),x]),y[i-4:i+1],rcond=None)[0];residual=y[i-4:i+1]-(intercept+slope*x)
            self.assertAlmostEqual(values[0][i],slope,places=10);self.assertAlmostEqual(values[1][i],intercept+4*slope,places=10);self.assertAlmostEqual(values[3][i],np.sqrt(np.mean(residual**2)),places=8)
        self.assertAlmostEqual(values[0][-1],1.93)
    def test_large_window_regression_and_quality(self):
        x=np.arange(7200);y=5000+.01*x+2*np.sin(x/17);n=6900;values=subject.rolling_regression(y,np.zeros(len(y),int),n);xx=np.arange(n);intercept,slope=np.linalg.lstsq(np.column_stack([np.ones(n),xx]),y[-n:],rcond=None)[0];residual=y[-n:]-(intercept+slope*xx)
        self.assertAlmostEqual(values[0][-1],slope,places=9);self.assertAlmostEqual(values[4][-1],slope*(n-1)/np.sqrt(np.mean(residual**2)),places=5)
    def test_constant_regression_quality_undefined(self):
        values=subject.rolling_regression(np.full(10,100.),np.zeros(10,int),5);self.assertEqual(values[0][-1],0);self.assertTrue(np.isnan(values[4][-1]))
    def test_future_extreme_excludes_current_and_includes_endpoint(self):
        x=np.array([999,1,7,3,5.]);actual=subject.future_extreme(x,2,True);np.testing.assert_allclose(actual,[7,7,5,np.nan,np.nan],equal_nan=True)
    def test_future_low_and_short_tail(self):
        x=np.array([-999,4,2,8.]);np.testing.assert_allclose(subject.future_extreme(x,2,False),[2,2,np.nan,np.nan],equal_nan=True)
    def test_maintenance_removal_preserves_roll_identity(self):
        t=pd.DataFrame({'timestamp_utc':pd.to_datetime(['2026-10-01T20:59:00Z','2026-10-01T21:30:00Z','2026-10-01T22:00:00Z']),'close':[100.,105.,110.],'roll_transition':[False,True,False],'is_complete':[True]*3})
        with patch.object(subject.pq,'read_table',return_value=pa.Table.from_pandas(t)):
            actual=subject.read_source(list(t.columns))
        self.assertEqual(actual.close.tolist(),[100.,110.]);self.assertEqual(actual.source_roll_segment.tolist(),[0,1]);self.assertEqual(actual.attrs['original_audit']['maintenance_rows_removed'],1)
    def test_quintile_edges_and_exact_boundary(self):
        x=np.arange(10.);edges=subject.qcut_edges(x,np.ones(10,bool));np.testing.assert_allclose(edges,[1.8,3.6,5.4,7.2]);self.assertEqual(subject.buckets(np.array([edges[0]]),edges)[0],2)

def load_independent(source):
    f=pq.read_table(source,columns=['timestamp_utc','high','low','close','roll_transition','is_complete']).to_pandas();f=f.sort_values('timestamp_utc').loc[lambda x:x.is_complete.fillna(False)].reset_index(drop=True)
    segments=np.cumsum(f.roll_transition.to_numpy(bool));local=pd.DatetimeIndex(f.timestamp_utc).tz_convert('America/New_York');hour=local.hour.to_numpy();minute=((hour-18)%24)*60+local.minute.to_numpy();keep=minute<1380;f=f.loc[keep].reset_index(drop=True);segments=segments[keep];minute=minute[keep];local=local[keep]
    dates=(local.normalize()+pd.to_timedelta((local.hour>=18).astype(int),unit='D')).date;years=np.array([d.year for d in dates]);labels=np.select([years<=2014,years<=2022,years<=2024],['HISTORICAL_ROBUSTNESS','DISCOVERY','VALIDATION'],default='HOLDOUT');return f,segments,minute,dates,years,labels

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();folder=subject.PACKAGE/'results';cfg=subject.CFG;assert hashlib.sha256(a.input.read_bytes()).hexdigest()==cfg['source_sha256']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MathematicalChecks));assert result.wasSuccessful()
    frame,segment,minute,day,year,period=load_independent(a.input);close=frame.close.to_numpy();high=frame.high.to_numpy();low=frame.low.to_numpy();specs=json.loads((subject.PACKAGE/'frozen-definitions.json').read_text());saved=pd.concat([pd.read_csv(folder/'long_regime_results.csv'),pd.read_csv(folder/'short_regime_results.csv')],ignore_index=True);rng=np.random.default_rng(cfg['random_seed']);compared=0;rows=0
    def check(actual,expected,name):
        nonlocal compared
        assert math.isclose(float(actual),float(expected),rel_tol=2e-8,abs_tol=1e-7),(name,actual,expected);compared+=1
    for key,spec in specs.items():
        h=int(key.split('_')[1]);n=spec['length'];k=spec['slope_horizon'];ma=direct_ma(close,segment,n,spec['ma_type']);slope=np.r_[np.full(k,np.nan),ma[k:]-ma[:-k]];slope[np.r_[np.ones(k,bool),segment[k:]!=segment[:-k]]]=np.nan;signal=(close>ma)&(slope>0) if key.startswith('long') else (close<ma)&(slope<0)
        future=np.r_[close[h:],np.full(h,np.nan)];valid=np.r_[(segment[h:]==segment[:-h])&(period[h:]==period[:-h]),np.zeros(h,bool)];raw=(future-close)/close;raw[~valid]=np.nan
        # Reversed pandas rolling extrema provide a second implementation of forward windows.
        maximum=pd.Series(high[::-1]).rolling(h,min_periods=h).max().to_numpy()[::-1];maximum=np.r_[maximum[1:],np.nan];minimum=pd.Series(low[::-1]).rolling(h,min_periods=h).min().to_numpy()[::-1];minimum=np.r_[minimum[1:],np.nan]
        for pname in ['DISCOVERY','VALIDATION','HOLDOUT','HISTORICAL_ROBUSTNESS']:
            universe=(period==pname)&np.isfinite(raw)
            for side in ['long','short']:
                ret=raw if side=='long' else -raw;chosen=universe&signal;indices=np.flatnonzero(chosen);r=saved.loc[(saved.candidate==key)&(saved.period==pname)&(saved.direction==side.upper())].iloc[0]
                baseline=pd.Series(ret[universe]).groupby(minute[universe]).mean();positive=pd.Series(ret[universe]>0).groupby(minute[universe]).mean();b=baseline.reindex(minute[chosen]).to_numpy();bp=positive.reindex(minute[chosen]).to_numpy();ex=ret[chosen]-b;daily=pd.Series(ex).groupby(day[chosen]).mean().to_numpy();boots=daily[rng.integers(0,len(daily),(cfg['bootstrap_repetitions'],len(daily)))].mean(axis=1);mfe=np.maximum(maximum-close,0) if side=='long' else np.maximum(close-minimum,0);mae=np.maximum(close-minimum,0) if side=='long' else np.maximum(maximum-close,0)
                values={'raw_observations':len(indices),'distinct_trading_days':len(set(day[chosen])),'distinct_years':len(set(year[chosen])),'positive_pct':100*np.mean(ret[chosen]>0),'matched_baseline_positive_pct':100*np.mean(bp),'excess_positive_pp':100*(np.mean(ret[chosen]>0)-np.mean(bp)),'mean_return_pct':100*np.mean(ret[chosen]),'median_return_pct':100*np.median(ret[chosen]),'matched_excess_mean_bp':10000*np.mean(ex),'day_balanced_mean_excess_bp':10000*np.mean(daily),'day_block_ci_low_bp':10000*np.quantile(boots,.025),'day_block_ci_high_bp':10000*np.quantile(boots,.975),'mean_MFE_points':np.mean(mfe[chosen]),'median_MFE_points':np.median(mfe[chosen]),'mean_MAE_points':np.mean(mae[chosen]),'median_MAE_points':np.median(mae[chosen]),'MFE_MAE_ratio':np.mean(mfe[chosen])/np.mean(mae[chosen])}
                for q in [10,25,75,90]:values[f'p{q}_return_pct']=100*np.quantile(ret[chosen],q/100)
                for name,value in values.items():check(value,r[name],key+'/'+pname+'/'+side+'/'+name)
                rows+=1
        print('Independent recount passed: '+key,flush=True)
    # The full searched grid is retained; validate count/probability partitions and finite means.
    all_candidates=pd.read_csv(folder/'candidate_summary.csv');targets=pd.read_csv(folder/'target_stop_diagnostics.csv');assert np.isfinite(all_candidates.loc[all_candidates.raw_observations.gt(0),'mean_return_pct']).all();np.testing.assert_allclose(targets.target_first_pct+targets.stop_first_pct+targets.unresolved_or_no_touch_pct,100,atol=2e-8)
    audit={'passed':True,'invented_mathematical_checks':result.testsRun,'independent_fixed_rule_period_side_rows':rows,'independent_metric_comparisons':compared,'candidate_grid_rows':len(all_candidates),'bucket_rows':len(pd.read_csv(folder/'bucket_monotonicity.csv')),'target_stop_aggregate_rows':len(targets),'same_input_sha256':True,'note':'Full grid rerun in reproduce.py; all 32 fixed-rule period/side distributions independently recounted for 21 metrics each, including whole-session bootstrap centers/intervals. Grid outcomes themselves are not 32 independent market samples. Target/stop table partition checked; not separately recounted for every source path.'}
    (folder/'verification.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8');print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
