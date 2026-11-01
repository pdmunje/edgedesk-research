"""Independent standard-library recount plus invented boundary cases."""
import argparse,bisect,csv,json,math,statistics,unittest
from datetime import date,timedelta
from pathlib import Path
import pandas as pd
import reproduce as target
def monday(d):return d-timedelta(days=d.weekday())
def read(folder):
    data={}
    for name,file in target.FILES.items():
        with (folder/file).open(encoding='utf-8-sig',newline='') as f:source=list(csv.DictReader(f))
        rows=[{'date':date.fromisoformat(r['time']),**{k:float(r[k]) for k in ['open','high','low','close']}} for r in source]
        assert [r['date'] for r in rows]==sorted(set(r['date'] for r in rows))
        assert all(0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] and all(math.isfinite(r[k]) for k in ['open','high','low','close']) for r in rows)
        data[name]=rows
    es={};sk={};returns=[];last=None;end=date(2026,9,21)
    for r in data['es']:
        if last is not None:returns.append(100*(r['close']/last-1))
        last=r['close'];w=monday(r['date'])
        if w>end:continue
        if w not in es:es[w]={'open':r['open'],'high':r['high'],'low':r['low']}
        es[w].update(high=max(es[w]['high'],r['high']),low=min(es[w]['low'],r['low']),close=r['close'],vol=statistics.stdev(returns[-20:]) if len(returns)>=20 else None)
    for r in data['skew']:
        w=monday(r['date'])
        if w<=end:assert w not in sk;sk[w]=r['close']
    weeks=sorted(sk);rows=[]
    for w in sorted(set(es)&set(sk)):
        calendar=[sk.get(w-timedelta(weeks=j)) for j in range(104,0,-1)]
        position=weeks.index(w);reported=[sk[x] for x in weeks[position-104:position]] if position>=104 else []
        r={'date':w.isoformat(),'year':w.year,'week_row':(w-min(es)).days//7,'vol':es[w]['vol']}
        for key,history in [('rank',calendar),('reported_rank',reported)]:
            r[key]=100*sum(x<=sk[w] for x in history)/104 if len(history)==104 and all(x is not None for x in history) else None
        if r['vol'] is not None:r['vol_band']=bisect.bisect_right([0,.5,1,1.5,2,3],r['vol'])-1
        for h in [1,4]:
            forward=[es.get(w+timedelta(weeks=j)) for j in range(1,h+1)]
            if all(x is not None for x in forward):
                entry=forward[0]['open'];points=max(x['high'] for x in forward)-min(x['low'] for x in forward)
                r[h]={'range':100*points/entry,'points':points,'direction':100*(forward[-1]['close']/entry-1)}
        rows.append(r)
    return rows
def eligible(rows,history):
    g=[dict(r) for r in rows if r[history] is not None and r['vol'] is not None]
    for r in g:
        r['group']='low' if r[history]<=20 else 'high' if r[history]>=80 else 'middle'
        for h in [1,4]:
            if h not in r:continue
            peers=[x[h]['range'] for x in g if h in x and x['year']==r['year'] and x['vol_band']==r['vol_band'] and x['date']!=r['date']]
            r['peer_count'+str(h)]=len(peers)
            if peers:r['matched'+str(h)]=statistics.mean(peers)
    return g
def spaced(rows,h):
    result=[]
    for r in rows:
        if not result or r['week_row']>=result[-1]['week_row']+h:result.append(r)
    return result
def describe(rows,h):
    g=[r for r in rows if h in r];m=[r for r in g if 'matched'+str(h) in r]
    if not g:return {'events':0}
    x=[r[h]['range'] for r in g];d=[r[h]['direction'] for r in g];points=[r[h]['points'] for r in g]
    out={'events':len(g),'mean_range_pct':statistics.mean(x),'median_range_pct':statistics.median(x),'mean_range_points':statistics.mean(points),'mean_direction_pct':statistics.mean(d),'positive_events':sum(v>0 for v in d),'positive_pct':100*sum(v>0 for v in d)/len(g),'mean_trailing_daily_sd_pct':statistics.mean(r['vol'] for r in g),'matched_events':len(m),'unmatched_events':len(g)-len(m),'first_signal_week':g[0]['date'],'last_signal_week':g[-1]['date']}
    if m:out.update(matched_signal_mean_range_pct=statistics.mean(r[h]['range'] for r in m),peer_mean_range_pct=statistics.mean(r['matched'+str(h)] for r in m),excess_range_pct_points=statistics.mean(r[h]['range']-r['matched'+str(h)] for r in m),minimum_peer_weeks=min(r['peer_count'+str(h)] for r in m),median_peer_weeks=statistics.median(r['peer_count'+str(h)] for r in m))
    return out
class Examples(unittest.TestCase):
    def test_current_excluded_and_exact_cutoffs(self):
        old=list(range(1,105));self.assertAlmostEqual(target.rank(pd.Series(old+[20])).iloc[-1],100*20/104)
        self.assertAlmostEqual(target.rank(pd.Series(old+[104])).iloc[-1],100)
    def test_ties_count_less_or_equal(self):self.assertEqual(target.rank(pd.Series([10.]*104+[10.])).iloc[-1],100)
    def test_missing_history_not_filled(self):self.assertTrue(pd.isna(target.rank(pd.Series([10.]*103+[float('nan'),10.])).iloc[-1]))
    def test_not_enough_history(self):self.assertTrue(pd.isna(target.rank(pd.Series([10.]*104)).iloc[-1]))
    def test_spacing_uses_calendar_not_row_count(self):
        f=pd.DataFrame({'week_row':[0,1,4,8]},index=list('abcd'));self.assertEqual(target.spaced(f,4).index.tolist(),['a','c','d'])
    def test_holiday_mapping(self):self.assertEqual(monday(date(2026,9,8)),date(2026,9,7))
    def test_volatility_cutoff_exact(self):self.assertEqual(bisect.bisect_right([0,.5,1,1.5,2,3],1)-1,2)
    def test_total_range_is_not_sum_of_ranges(self):
        bars=[{'high':110,'low':95},{'high':108,'low':90}];self.assertEqual(max(x['high'] for x in bars)-min(x['low'] for x in bars),20)
        self.assertNotEqual(20,sum(x['high']-x['low'] for x in bars))
    def test_flat_is_not_positive(self):self.assertEqual(sum(x>0 for x in [0,1,-1]),1)
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',required=True,type=Path);a=p.parse_args();saved=json.loads((target.HERE/'results/summary.json').read_text());rows=read(a.input_dir);comparisons=0
    def compare(actual,expected):
        nonlocal comparisons
        assert actual.keys()==expected.keys(),(actual.keys(),expected.keys())
        for k,v in actual.items():
            if isinstance(v,(int,float)):assert math.isclose(v,expected[k],rel_tol=2e-10,abs_tol=2e-10),(k,v,expected[k])
            else:assert v==expected[k],(k,v,expected[k])
            comparisons+=1
    for history in ['rank','reported_rank']:
        g=eligible(rows,history)
        for group in ['low','middle','high','all']:
            chosen=[r for r in g if r['group']==group or group=='all'];first=[]
            for i,r in enumerate(g):
                hit=r['group']==group or group=='all';prior=i>0 and (g[i-1]['group']==group or group=='all') and r['week_row']==g[i-1]['week_row']+1
                if hit and not prior:first.append(r)
            actual=saved['results'][history][group];assert len(chosen)==actual['signal_weeks'] and len(first)==actual['first_run_weeks']
            for h in [1,4]:
                valid=[r for r in chosen if h in r]
                for method,v in [('all_weeks',valid),('first_consecutive_group_week',first),('nonoverlapping_by_horizon',spaced(valid,h))]:compare(describe(v,h),actual['horizons'][str(h)][method])
    g=eligible(rows,'rank')
    for period,lo,hi in [('1997_2009',1997,2009),('2010_2019',2010,2019),('2020_2026',2020,2026)]:
        for group in ['low','middle','high','all']:
            for h in [1,4]:compare(describe([r for r in g if lo<=r['year']<=hi and (r['group']==group or group=='all')],h),saved['periods'][period][group][str(h)])
    # Compare every intermediate rank, volatility and outcome too, not only rounded headlines.
    frame,checks=target.prepare(a.input_dir)
    for r in rows:
        s=frame.loc[r['date']]
        for key in ['rank','reported_rank','vol']:
            if r[key] is None:assert pd.isna(s[key])
            else:assert math.isclose(r[key],s[key],rel_tol=2e-10,abs_tol=2e-10)
            comparisons+=1
        for h in [1,4]:
            for metric in ['range','points','direction']:
                if h in r:assert math.isclose(r[h][metric],s[f'{metric}{h}'],rel_tol=2e-10,abs_tol=2e-10)
                else:assert pd.isna(s[f'{metric}{h}'])
                comparisons+=1
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Examples));assert result.wasSuccessful()
    assert saved['source_sha256']=={name:target.fingerprint(a.input_dir/file) for name,file in target.FILES.items()}
    result={'independent_numeric_or_date_comparisons':comparisons,'invented_boundary_tests':result.testsRun,'aggregate_rows':saved['aggregate_rows'],'source_fingerprints_verified':True,'passed':True}
    (target.HERE/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
