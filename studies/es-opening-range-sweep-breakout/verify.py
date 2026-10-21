"""Independent array-based reconstruction of every strict parent outcome and summaries."""
import argparse,hashlib,itertools,json,math,unittest
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import reproduce as s

def independent_trade(op,hi,lo,cl,opening,atr,side,sweep):
    upper=max(hi[:opening]);lower=min(lo[:opening]);after=np.arange(opening,len(cl));touch=(lo[after]<=lower) if side=='long' else (hi[after]>=upper);earlier=np.r_[False,np.cumsum(touch[:-1])>0];breaks=(cl[after]>upper) if side=='long' else (cl[after]<lower);hits=np.flatnonzero(breaks&(earlier if sweep else True))
    if not len(hits):return None
    entry=after[hits[0]]+1
    if entry==len(cl):return None
    raw=min(op[0],upper-atr) if side=='long' else max(op[0],lower+atr);stop=math.floor(raw*4+1e-10)/4 if side=='long' else math.ceil(raw*4-1e-10)/4
    if (op[entry]<=stop if side=='long' else op[entry]>=stop):return None
    reached=np.flatnonzero(lo[entry:]<=stop if side=='long' else hi[entry:]>=stop);stopped=bool(len(reached));exit=entry+reached[0] if stopped else len(cl)-1;price=(min(op[exit],stop) if side=='long' else max(op[exit],stop)) if stopped else cl[-1];return ((price-op[entry]) if side=='long' else (op[entry]-price)),stopped

def fixture():
    q=pd.DataFrame({'session_minute':np.arange(6),'open':[100.,100,102,103,103,103],'high':[101.,103,103,104,105,105],'low':[99.,98,101,102,102,102],'close':[100.,102,102,103,104,104]});m={'start':0,'open':100.,'full':True,'strict_atr9_prior':1.};return q,m

class MathematicalChecks(unittest.TestCase):
    def test_earlier_touch_not_same_bar(self):
        q,m=fixture();plain,_=s.strict_trade(q,m,1,9,'long',False);sweep,_=s.strict_trade(q,m,1,9,'long',True);self.assertEqual(plain,(2.,False));self.assertEqual(sweep,(1.,False))
    def test_stop_active_on_entry_minute(self):
        q,m=fixture();q.loc[3,'low']=99.;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-3.,True))
    def test_gap_through_stop_uses_open(self):
        q,m=fixture();q.loc[4,['open','low']]=[98.,97.];self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-5.,True))
    def test_invalid_open_risk_cancels(self):
        q,m=fixture();q.loc[3,'open']=99.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_last_minute_break_has_no_next_open(self):
        q,m=fixture();q.loc[1:4,'close']=100.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_short_symmetry(self):
        q,m=fixture();q['open']=200-q.open;q['close']=200-q.close;high=200-q.low;low=200-q.high;q['high']=high;q['low']=low;self.assertEqual(s.strict_trade(q,m,1,9,'short',True)[0],(1.,False))
    def test_tick_stop_rounding(self):
        q,m=fixture();m['strict_atr9_prior']=1.12;q.loc[3,'low']=99.8;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(1.,False));q.loc[3,'low']=99.7;self.assertEqual(s.strict_trade(q,m,1,9,'long',True)[0],(-3.25,True))
    def test_sweep_must_be_after_opening_range(self):
        q,m=fixture();q.loc[1:,'low']=100.;self.assertIsNone(s.strict_trade(q,m,1,9,'long',True)[0])
    def test_missing_prior_atr(self):
        q,m=fixture();m['strict_atr9_prior']=np.nan;trade,eligible=s.strict_trade(q,m,1,9,'long',False);self.assertIsNone(trade);self.assertFalse(eligible)
    def test_incomplete_parent_rejected(self):
        q,m=fixture();m['full']=False;self.assertFalse(s.strict_trade(q,m,1,9,'long',False)[1])
    def test_wilder_seed_and_update(self):
        x=s.legacy.wilder(np.array([2.,4.,6.,8.]),3,np.zeros(4));np.testing.assert_allclose(x,[np.nan,np.nan,4,16/3],equal_nan=True)
    def test_cost_is_per_completed_round_trip(self):
        self.assertAlmostEqual(.25-s.CFG['cost_points'],-.34);self.assertAlmostEqual(.5+.09,s.CFG['cost_points'])

def compare(actual,expected,label,counter):
    if pd.isna(actual) and pd.isna(expected):counter[0]+=1;return
    assert math.isclose(float(actual),float(expected),rel_tol=2e-8,abs_tol=2e-7),(label,actual,expected);counter[0]+=1

def bootstrap(values,dates,key):
    # Dictionary groups rather than the production DataFrame aggregation.
    sums={};counts={}
    for value,date in zip(values,dates):sums[date]=sums.get(date,0)+value;counts[date]=counts.get(date,0)+1
    days=sorted(sums);total=np.array([sums[d] for d in days]);n=np.array([counts[d] for d in days]);seed=int.from_bytes(hashlib.sha256((str(s.CFG['seed'])+'|'+key).encode()).digest()[:8],'little');rng=np.random.default_rng(seed);draw=rng.integers(len(days),size=(s.CFG['bootstrap_repetitions'],len(days)));return np.quantile(total[draw].sum(1)/n[draw].sum(1),[.025,.975])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);args=parser.parse_args();assert hashlib.sha256(args.input.read_bytes()).hexdigest()==s.CFG['source_sha256'];test=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MathematicalChecks));assert test.wasSuccessful()
    raw=pq.read_table(args.input,columns=['timestamp_utc','open','high','low','close','underlying_contract','roll_transition','is_complete']).to_pandas().sort_values('timestamp_utc',kind='stable');raw=raw.loc[raw.is_complete.fillna(False)].reset_index(drop=True);seg=raw.roll_transition.fillna(False).cumsum().to_numpy();local=pd.DatetimeIndex(raw.timestamp_utc).tz_convert('America/New_York');minute=((local.hour.to_numpy()-18)%24)*60+local.minute.to_numpy();dates=np.array((local.normalize()+pd.to_timedelta((local.hour>=18).astype(int),unit='D')).date,dtype='datetime64[D]').astype('int64');keep=minute<1380;raw=raw.loc[keep].reset_index(drop=True);seg=seg[keep];minute=minute[keep];dates=dates[keep]
    folder=s.PACKAGE/'results';saved=pd.read_csv(folder/'summary.csv');paired=pd.read_csv(folder/'paired-comparison.csv');annual=pd.read_csv(folder/'annual.csv');expected_hashes=json.loads((folder/'strict-fingerprints.json').read_text());counter=[0];summary_rows=0;annual_rows=0;paired_rows=0;intervals=0;hashes=0
    for family,ors in s.CFG['or_lengths'].items():
        familykeep=minute<930 if family=='930M' else np.ones(len(raw),bool);d=raw.loc[familykeep];mm=minute[familykeep];ss=seg[familykeep];dd=dates[familykeep];slot=mm//60 if family=='1H' else mm//240 if family=='4H' else np.zeros(len(d),int);starts=np.r_[0,np.flatnonzero((dd[1:]!=dd[:-1])|(slot[1:]!=slot[:-1]))+1];ends=np.r_[starts[1:],len(d)];N=len(starts);specs=list(itertools.product(ors,s.CFG['atr_lengths'],['long','short']));shape=(N,len(specs));gross={m:np.full(shape,np.nan) for m in ['strict_sweep','strict_plain']};stopped={m:np.zeros(shape,bool) for m in gross};eligible=np.zeros(shape,bool);op=d.open.to_numpy();hi=d.high.to_numpy();lo=d.low.to_numpy();cl=d.close.to_numpy();contract=d.underlying_contract.to_numpy();days=dd[starts];years=pd.DatetimeIndex(days.astype('datetime64[D]')).year.to_numpy();labels=np.select([years<=2015,years<=2022],['historical_2010_2015','development_2016_2022'],default='later_2023_2026');states={n:{'segment':None,'previous':None,'tr':[],'value':np.nan} for n in s.CFG['atr_lengths']}
        for i,(a,b) in enumerate(zip(starts,ends)):
            start=int(slot[a])*(60 if family=='1H' else 240) if family in ['1H','4H'] else 0;duration=60 if family=='1H' else min(240,1380-start) if family=='4H' else 930 if family=='930M' else 1380
            if family=='4H' and duration!=240:continue
            full=(b-a==duration and mm[a]==start and mm[b-1]==start+duration-1 and np.all(contract[a:b]==contract[a]) and ss[a]==ss[b-1]);atrs={}
            for n,state in states.items():
                if not full:state.update(segment=None,previous=None,tr=[],value=np.nan);atrs[n]=np.nan;continue
                if state['segment']!=ss[a]:state.update(segment=ss[a],previous=None,tr=[],value=np.nan)
                atrs[n]=state['value'];high=float(max(hi[a:b]));low=float(min(lo[a:b]));prev=state['previous'];tr=high-low if prev is None else max(high-low,abs(high-prev),abs(low-prev));state['tr'].append(tr)
                if len(state['tr'])==n:state['value']=sum(state['tr'])/n
                elif len(state['tr'])>n:state['value']=(state['value']*(n-1)+tr)/n
                state['previous']=float(cl[b-1])
            if not full:continue
            for j,(opening,n,side) in enumerate(specs):
                if not np.isfinite(atrs[n]) or atrs[n]<=0:continue
                eligible[i,j]=True
                for model,sweep in [('strict_sweep',True),('strict_plain',False)]:
                    event=independent_trade(op[a:b],hi[a:b],lo[a:b],cl[a:b],opening,atrs[n],side,sweep)
                    if event is not None:gross[model][i,j]=event[0];stopped[model][i,j]=event[1]
        for model in gross:
            for name,array in [('gross',np.nan_to_num(np.round(gross[model],8),nan=1e12).astype('<f8')),('eligible',eligible.astype('u1')),('stopped',stopped[model].astype('u1'))]:assert hashlib.sha256(array.tobytes()).hexdigest()==expected_hashes[family+'|'+model][name],(family,model,name);hashes+=1
        for j,(opening,n,side) in enumerate(specs):
            for model in gross:
                vals=gross[model][:,j];valid=np.isfinite(vals)
                for pname in s.CFG['periods']:
                    chosen=valid if pname=='all_2010_2026' else valid&(labels==pname);net=vals[chosen]-.59;row=saved.loc[(saved.family==family)&(saved.or_minutes==opening)&(saved.atr_length==n)&(saved.side==side)&(saved.model==model)&(saved.period==pname)].iloc[0]
                    values={'trades':chosen.sum(),'signal_days':len(np.unique(days[chosen])),'gross_avg_points':np.mean(vals[chosen]) if chosen.any() else np.nan,'net_avg_points':np.mean(net) if chosen.any() else np.nan,'net_win_pct':100*np.mean(net>0) if chosen.any() else np.nan,'stop_pct':100*np.mean(stopped[model][chosen,j]) if chosen.any() else np.nan}
                    for field,value in values.items():compare(row[field],value,(family,opening,n,side,model,pname,field),counter)
                    if opening==ors[0] and n==9 and side=='long' and pname in ['development_2016_2022','later_2023_2026'] and chosen.any():
                        ci=bootstrap(net,days[chosen],f'{family}|{opening}|{n}|{side}|{model}|{pname}');compare(row.net_ci_low,ci[0],'CI low',counter);compare(row.net_ci_high,ci[1],'CI high',counter);intervals+=1
                    summary_rows+=1
                for yy in sorted(set(years)):
                    chosen=valid&(years==yy);row=annual.loc[(annual.family==family)&(annual.or_minutes==opening)&(annual.atr_length==n)&(annual.side==side)&(annual.model==model)&(annual.year==yy)].iloc[0];compare(row.trades,chosen.sum(),'Annual count',counter);compare(row.net_avg_points,np.mean(vals[chosen]-.59) if chosen.any() else np.nan,'Annual mean',counter);annual_rows+=1
            sweeps=np.where(np.isfinite(gross['strict_sweep'][:,j]),gross['strict_sweep'][:,j]-.59,0);plains=np.where(np.isfinite(gross['strict_plain'][:,j]),gross['strict_plain'][:,j]-.59,0)
            for pname in s.CFG['periods']:
                e=eligible[:,j] if pname=='all_2010_2026' else eligible[:,j]&(labels==pname);row=paired.loc[(paired.family==family)&(paired.or_minutes==opening)&(paired.atr_length==n)&(paired.side==side)&(paired.period==pname)].iloc[0];delta=sweeps[e]-plains[e]
                values={'eligible_parents':e.sum(),'sweep_trades':np.isfinite(gross['strict_sweep'][e,j]).sum(),'plain_trades':np.isfinite(gross['strict_plain'][e,j]).sum(),'sweep_net_per_parent':sweeps[e].mean() if e.any() else np.nan,'plain_net_per_parent':plains[e].mean() if e.any() else np.nan,'sweep_minus_plain_per_parent':delta.mean() if e.any() else np.nan}
                for field,value in values.items():compare(row[field],value,'Paired '+field,counter)
                if opening==ors[0] and n==9 and side=='long' and pname in ['development_2016_2022','later_2023_2026'] and e.any():
                    ci=bootstrap(delta,days[e],f'paired|{family}|{opening}|{n}|{side}|{pname}');compare(row.difference_ci_low,ci[0],'Paired interval low',counter);compare(row.difference_ci_high,ci[1],'Paired interval high',counter);intervals+=1
                paired_rows+=1
        print('Independent full strict replay passed: '+family,flush=True)
    result={'passed':True,'mathematical_checks':test.testsRun,'strict_matrix_fingerprints':hashes,'strict_summary_rows':summary_rows,'strict_annual_rows':annual_rows,'paired_comparison_rows':paired_rows,'independent_numeric_comparisons':counter[0],'independently_recounted_interval_rows':intervals,'source_sha256_unchanged':hashlib.sha256(args.input.read_bytes()).hexdigest()==s.CFG['source_sha256'],'note':'Independent grouping, complete-parent prior ATR history, all strict per-parent gross outcomes, stop flags and eligible masks verified by matrix fingerprints. All strict summary/annual centers/counts and every paired comparison checked; selected development/later intervals independently recounted. Original replay agreement with saved source checked separately. No multiplicity-adjusted significance or live execution claim.'};(folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
