"""Separate csv/date/statistics recount and invented boundary examples."""
import argparse,csv,json,math,statistics,unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
import pandas as pd
import reproduce as subject

def week(d):return d-timedelta(days=d.weekday())
def independent(folder):
    sources={}
    for name,file in subject.FILES.items():
        with (folder/file).open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
        dates=[r['time'] for r in raw];assert dates==sorted(set(dates))
        rows=[]
        for r in raw:
            d=date.fromisoformat(r['time']);values={k:float(r[k]) for k in ['open','high','low','close']}
            assert all(math.isfinite(v) and v>0 for v in values.values());assert values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']
            rows.append({'date':d,'week':week(d),**values})
        sources[name]=rows
    end=date(2026,9,21);es={};sk={}
    for r in sources['es']:
        if r['week']>end:continue
        w=r['week']
        if w not in es:es[w]={'open':r['open'],'close':r['close']}
        else:es[w]['close']=r['close']
    for r in sources['skew']:
        if r['week']<=end:
            assert r['week'] not in sk;sk[r['week']]=r['close']-r['open']
    z={};z_reported={};skdates=sorted(sk)
    for i,w in enumerate(skdates):
        calendar=[sk.get(w-timedelta(weeks=j)) for j in range(104,0,-1)]
        if all(x is not None for x in calendar) and statistics.stdev(calendar)>0:z[w]=(sk[w]-statistics.mean(calendar))/statistics.stdev(calendar)
        if i>=104:
            old=[sk[x] for x in skdates[i-104:i]]
            if statistics.stdev(old)>0:z_reported[w]=(sk[w]-statistics.mean(old))/statistics.stdev(old)
    start=min(es);rows=[]
    for w in sorted(set(es)&set(sk)):
        if w<start or w>end:continue
        r={'date':w.isoformat(),'week':w,'week_row':(w-start).days//7,'year':w.year,'change':sk[w],'z':z.get(w),'z_reported':z_reported.get(w)}
        for h in [1,2,4,8,13]:
            forward=[es.get(w+timedelta(weeks=j)) for j in range(1,h+1)]
            if all(x is not None for x in forward):
                entry=forward[0]['open'];exit=forward[-1]['close'];r[h]=(100*(exit/entry-1),100*(exit-entry-1)/entry)
        rows.append(r)
    for r in rows:
        for h in [1,2,4,8,13]:
            if h in r:
                peers=[x[h][0] for x in rows if h in x and x['year']==r['year'] and x['date']!=r['date']];assert peers;r['matched'+str(h)]=statistics.mean(peers)
    return rows

def spaced(rows,gap):
    result=[]
    for r in rows:
        if not result or r['week_row']>=result[-1]['week_row']+gap:result.append(r)
    return result
def describe(rows,h):
    chosen=[r for r in rows if h in r]
    if not chosen:return {'events':0}
    values=[r[h][0] for r in chosen];net=[r[h][1] for r in chosen];reference=[r['matched'+str(h)] for r in chosen]
    return {'events':len(chosen),'mean_pct':statistics.mean(values),'median_pct':statistics.median(values),'positive_events':sum(v>0 for v in values),'positive_pct':100*sum(v>0 for v in values)/len(values),'mean_after_one_point_pct':statistics.mean(net),'same_year_other_week_mean_pct':statistics.mean(reference),'mean_excess_pct_points':statistics.mean(v-r for v,r in zip(values,reference)),'minimum_pct':min(values),'maximum_pct':max(values),'first_signal_week':chosen[0]['date'],'last_signal_week':chosen[-1]['date']}

class MadeUp(unittest.TestCase):
    def test_holiday_label_maps_to_monday(self):
        dates=pd.DatetimeIndex(['2026-09-07','2026-09-08','2026-09-09']);self.assertEqual(subject.monday(dates).strftime('%Y-%m-%d').tolist(),['2026-09-07']*3)
    def test_current_change_excluded_and_sample_sd(self):
        previous=[-1.,1.]*52;s=pd.Series(previous+[-2.,-20.]);z=subject.standardized(s)
        self.assertTrue(pd.isna(z.iloc[103]));self.assertAlmostEqual(z.iloc[104],-2/statistics.stdev(previous))
        altered=pd.Series(previous+[-200.]);self.assertAlmostEqual(subject.standardized(altered).iloc[104],100*z.iloc[104])
    def test_missing_history_not_filled(self):
        old=[-1.,1.]*52;old[30]=float('nan');self.assertTrue(pd.isna(subject.standardized(pd.Series(old+[-2.])).iloc[-1]))
    def test_zero_sd_is_undefined(self):self.assertTrue(pd.isna(subject.standardized(pd.Series([1.]*104+[-2.])).iloc[-1]))
    def test_exact_cutoffs_and_missing_z(self):
        f=pd.DataFrame({'change':[-4.99,-5.,-6.],'z':[-1.49,-1.5,float('nan')]});m=subject.signals(f)
        self.assertEqual(m['change_le5'].tolist(),[False,True,True]);self.assertEqual(m['normalized_le1_5'].tolist(),[False,True,False])
    def test_next_week_open_and_holiday_session(self):
        dates=['2026-09-07','2026-09-11','2026-09-15','2026-09-18','2026-09-21','2026-09-25']
        es=pd.DataFrame({'time':dates,'open':[90,100,110,113,121,125],'high':[101,106,114,121,124,131],'low':[89,99,109,112,120,124],'close':[100,105,112,120,123,130]})
        sk=pd.DataFrame({'time':['2026-09-08','2026-09-14','2026-09-21'],'open':[150.,150.,150.],'high':[160.,160.,160.],'low':[130.,130.,130.],'close':[145.,145.,145.]})
        def reader(path):return es.copy() if Path(path).name==subject.FILES['es'] else sk.copy()
        with patch.object(subject.pd,'read_csv',side_effect=reader):f,_=subject.load(Path('invented-input'))
        self.assertEqual(f.loc['2026-09-07','entry1'],110);self.assertAlmostEqual(f.loc['2026-09-07','r1'],100*(120/110-1));self.assertTrue(pd.isna(f.loc['2026-09-21','r1']))
    def test_exact_spacing_boundary(self):
        f=pd.DataFrame({'week_row':[0,1,3,4,7,8]});self.assertEqual(subject.spaced(f,4).week_row.tolist(),[0,4,8])
    def test_missing_calendar_week_interrupts_signal_run(self):
        f=pd.DataFrame({'change':[-5.,-5.,-5.],'z':[-2.,-2.,-2.],'week_row':[0,1,3]});f.index=['2026-01-05','2026-01-12','2026-01-26']
        for h in [1,2,4,8,13]:f[f'r{h}']=1.;f[f'n{h}']=.9;f[f'matched{h}']=0.
        result,_=subject.calculate(f);self.assertEqual(result['change_le5']['consecutive_signal_runs'],2)
    def test_missing_flat_and_one_point_cost(self):
        rows=[{'date':'a',1:(0.,-.1),'matched1':0.},{'date':'b',1:(2.,1.9),'matched1':0.},{'date':'c'}];v=describe(rows,1)
        self.assertEqual(v['events'],2);self.assertEqual(v['positive_events'],1);self.assertAlmostEqual(v['mean_after_one_point_pct'],.9)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUp));assert tests.wasSuccessful()
    base=Path(__file__).resolve().parent;s=json.loads((base/'results/summary.json').read_text());rows=independent(a.input_dir);frame,checks=subject.load(a.input_dir)
    assert checks==s['checks'];assert s['source_sha256']=={k:subject.fingerprint(a.input_dir/f) for k,f in subject.FILES.items()};assert [r['date'] for r in rows]==frame.index.tolist()
    matches=0
    def compare(actual,expected):
        nonlocal matches
        assert actual.keys()==expected.keys()
        for k,v in actual.items():
            if isinstance(v,(int,float)):assert math.isclose(v,expected[k],abs_tol=1e-9,rel_tol=1e-11),(k,v,expected[k])
            else:assert v==expected[k],(k,v,expected[k])
            matches+=1
    for row in rows:
        for key,column in [('z','z'),('z_reported','z_reported_observations')]:
            expected=row[key];actual=frame.loc[row['date'],column]
            assert (expected is None and pd.isna(actual)) or math.isclose(expected,actual,abs_tol=1e-9);matches+=1
        for h in [1,2,4,8,13]:
            if h in row:assert math.isclose(row[h][0],frame.loc[row['date'],f'r{h}'],abs_tol=1e-9);matches+=1
    conditions={**{f'change_le{abs(k)}':[r for r in rows if r['change']<=k] for k in [-2,-3,-4,-5,-6,-7,-8]},'normalized_le1_5':[r for r in rows if r['z'] is not None and r['z']<=-1.5]};aggregate=[]
    for name,chosen in conditions.items():
        dates={r['date'] for r in chosen};first=[];previous=False;last_row=None
        for row in rows:
            signal=row['date'] in dates
            if signal and (not previous or row['week_row']!=last_row+1):first.append(row)
            previous=signal;last_row=row['week_row']
        result=s['results'][name];assert result['signal_weeks']==len(chosen);assert result['consecutive_signal_runs']==len(first)
        for h in [1,2,4,8,13]:
            valid=[r for r in chosen if h in r]
            for method,events in [('all_signal_weeks',valid),('first_consecutive_signal_week',first),('nonoverlapping',spaced(valid,h)),('four_week_spacing',spaced(valid,4)),('eight_week_spacing',spaced(valid,8))]:
                values=describe(events,h);compare(values,result['horizons'][str(h)][method]);aggregate.append((name,h,method,values))
    for h in [1,2,4,8,13]:
        compare(describe(rows,h),s['baseline'][str(h)]);compare(describe([r for r in rows if r['z'] is not None],h),s['normalized_eligible_baseline'][str(h)])
        for key,events in [('previous104_calendar_weeks',conditions['normalized_le1_5']),('previous104_reported_observations',[r for r in rows if r['z_reported'] is not None and r['z_reported']<=-1.5])]:compare(describe(events,h),s['normalization_history_audit'][key][str(h)])
    for period,start,end in [('1997_2009',1997,2009),('2010_2019',2010,2019),('2020_2026',2020,2026)]:
        for name,events in [('fixed_le5',conditions['change_le5']),('normalized_le1_5',conditions['normalized_le1_5']),('all_weeks',rows),('normalized_eligible',[r for r in rows if r['z'] is not None])]:
            for h in [1,2,4,8,13]:compare(describe([r for r in events if start<=r['year']<=end],h),s['periods'][period][name][str(h)])
    with (base/'results/weekly_change_summary.csv').open() as f:csvrows=list(csv.DictReader(f))
    assert len(csvrows)==len(aggregate)==200
    for row,(name,h,method,values) in zip(csvrows,aggregate):
        assert (row['condition'],int(row['forward_calendar_weeks']),row['counting_method'])==(name,h,method)
        for k,v in values.items():
            if isinstance(v,(int,float)):assert math.isclose(float(row[k]),v,abs_tol=1e-9)
            else:assert row[k]==v
    p=s['results']['change_le5']['horizons']['4'];assert p['all_signal_weeks']['events']==155;assert round(p['all_signal_weeks']['mean_pct'],2)==1.76;assert p['nonoverlapping']['events']==110;assert round(p['nonoverlapping']['mean_pct'],2)==1.94
    record={'passed':True,'independent_value_matches':matches,'made_up_checks':tests.testsRun,'aggregate_rows_checked':200,'source_fingerprints_match':True,'source_comparison':'Fixed -5-point raw means, four/eight-week spacing and period results reproduce. Normalized old claim of 101 signals/+1.80% four-week mean does not reproduce: 89/+1.97% with complete104 calendar weeks; 111/+1.85% with previous104 reported observations. Old code is unavailable; cause unresolved.'}
    (base/'results/verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
