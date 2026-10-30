"""Independent CSV/date forward-window arithmetic and invented counting examples."""
import argparse,csv,json,math,statistics,unittest
from datetime import datetime
from pathlib import Path
import pandas as pd
from unittest.mock import patch
import reproduce as subject

def independent(folder):
    inputs={}
    for name,file in subject.FILES.items():
        with (folder/file).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        dates=[r['time'] for r in rows];assert dates==sorted(set(dates))
        for r in rows:
            r['close']=float(r['close']);assert math.isfinite(r['close'])
            if name=='es':
                for k in ['open','high','low']:r[k]=float(r[k])
                assert 0<r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']
            else:assert 0<=r['close']<=100
        inputs[name]={r['time']:r for r in rows}
    es=[r for d,r in inputs['es'].items() if d<='2026-10-01'];common=[]
    for i,r in enumerate(es):
        if not all(r['time'] in inputs[k] for k in ['b200','b50','b20','b5']):continue
        day=datetime.fromisoformat(r['time']);out={'date':r['time'],'es_row':i,'year':day.year,'weekday':day.weekday()}
        out.update({k:inputs[k][r['time']]['close'] for k in ['b200','b50','b20','b5']})
        for h in [1,3,5,10]:
            if i+h<len(es):out[h]=(100*(es[i+h]['close']/es[i+1]['open']-1),100*(es[i+h]['close']-es[i+1]['open']-1)/es[i+1]['open'])
        common.append(out)
    for r in common:
        for h in [1,3,5,10]:
            if h not in r:continue
            peers=[x[h][0] for x in common if h in x and x['year']==r['year'] and x['weekday']==r['weekday'] and x['date']!=r['date']]
            assert peers;r['matched'+str(h)]=statistics.mean(peers)
    return common

def spaced(rows,gap):
    selected=[]
    for r in rows:
        if not selected or r['es_row']-selected[-1]['es_row']>=gap:selected.append(r)
    return selected

def describe(rows,h):
    chosen=[r for r in rows if h in r]
    if not chosen:return {'events':0}
    returns=[r[h][0] for r in chosen];net=[r[h][1] for r in chosen];matched=[r['matched'+str(h)] for r in chosen]
    return {'events':len(chosen),'mean_pct':statistics.mean(returns),'median_pct':statistics.median(returns),
            'positive_events':sum(x>0 for x in returns),'positive_pct':100*sum(x>0 for x in returns)/len(chosen),
            'mean_after_one_point_pct':statistics.mean(net),'same_year_weekday_leave_one_out_mean_pct':statistics.mean(matched),
            'mean_excess_pct_points':statistics.mean(x-y for x,y in zip(returns,matched)),
            'minimum_pct':min(returns),'maximum_pct':max(returns),'first_signal_date':chosen[0]['date'],'last_signal_date':chosen[-1]['date']}

def high(values,L):
    return [None if i+1<L else values[i]>=max(values[i-L+1:i+1]) for i in range(len(values))]

def flags_and_signals(folder,rows):
    sources={}
    for name,file in subject.FILES.items():
        with (folder/file).open(encoding='utf-8-sig',newline='') as f:g=list(csv.DictReader(f))
        sources[name]=[(r['time'],float(r['close'])) for r in g if r['time']<='2026-10-01']
    for row in rows:row['mean']=statistics.mean(row[k] for k in ['b5','b20','b50','b200'])
    maps={}
    for L in [20,63,252]:
        maps[L]={}
        for name,source in sources.items():
            dates=[d for d,c in source];values=[c for d,c in source];current=high(values,L);recent=[]
            for i in range(len(current)):
                last=current[max(0,i-4):i+1]
                recent.append(None if len(last)<5 or any(x is None for x in last) else any(last))
            maps[L][name]={d:(now,rec) for d,now,rec in zip(dates,current,recent)}
        for row in rows:
            d=row['date'];row['high'+str(L)]=bool(maps[L]['es'][d][0]);same=[maps[L][k][d][0] for k in ['b5','b20','b50','b200']];recent=[maps[L][k][d][1] for k in ['b5','b20','b50','b200']]
            row['confirm'+str(L)]=None if any(x is None for x in same) else sum(same)
            row['recent'+str(L)]=None if any(x is None for x in recent) else sum(recent)
    masks={}
    for L in [20,63,252]:
        masks[f'L{L}_all_highs']=[r for r in rows if r['high'+str(L)]]
        for group,lo,hi in [('below50',-1,50),('50to80',50,80),('atleast80',80,101)]:masks[f'L{L}_mean_{group}']=[r for r in rows if r['high'+str(L)] and lo<=r['mean']<hi]
        eligible=[r for r in rows if r['high'+str(L)] and r['confirm'+str(L)] is not None]
        masks[f'L{L}_no_confirmation']=[r for r in eligible if r['confirm'+str(L)]==0]
        masks[f'L{L}_some_confirmation']=[r for r in eligible if r['confirm'+str(L)]>0]
        masks[f'L{L}_confirmation_eligible']=eligible
    return maps,masks

class MadeUp(unittest.TestCase):
    def test_full_history_and_ties(self):
        got=subject.high_flag(pd.Series([100.,110.,110.,105.,111.]),3).tolist()
        self.assertTrue(pd.isna(got[0]) and pd.isna(got[1]));self.assertEqual(got[2:],[True,False,True])
    def test_rolls_past_old_high(self):
        self.assertEqual(subject.high_flag(pd.Series([120.,100.,105.,110.]),3).iloc[-1],True)
    def test_mean80_is_not_all_series80(self):
        self.assertEqual(statistics.mean([100,90,80,50]),80);self.assertFalse(all(x>=80 for x in [100,90,80,50]))
        f=pd.DataFrame({'breadth_mean':[49.9,50.,79.9,80.]})
        for L in [20,63,252]:
            f[f'es_high{L}']=True;f[f'confirmation_valid{L}']=True;f[f'confirmed_count{L}']=0
        masks=subject.signals(f)
        self.assertEqual(masks['L20_mean_below50'].tolist(),[True,False,False,False])
        self.assertEqual(masks['L20_mean_50to80'].tolist(),[False,True,True,False])
        self.assertEqual(masks['L20_mean_atleast80'].tolist(),[False,False,False,True])
    def test_unavailable_confirmation_is_not_false(self):
        g=pd.DataFrame({'a':pd.Series([pd.NA,True],dtype='boolean'),'b':pd.Series([True,True],dtype='boolean')})
        self.assertEqual(g.notna().all(axis=1).tolist(),[False,True])
    def test_full_ES_calendar_and_missing_breadth(self):
        dates=['2026-01-05','2026-01-06','2026-01-07','2026-01-08'];es=pd.DataFrame({'time':dates,'open':[100,110,120,130],'high':[106,116,126,136],'low':[99,109,119,129],'close':[105,115,125,135]})
        for w in [200,50,20,5]:es[f'S&P 500 Stocks Above {w}-Day Average · INDEX: close']=50.
        breadth=pd.DataFrame({'time':[dates[0],dates[2],dates[3]],'open':50.,'high':50.,'low':50.,'close':50.})
        def reader(path):return es.copy() if Path(path).name==subject.FILES['es'] else breadth.copy()
        with patch.object(subject.pd,'read_csv',side_effect=reader):frame,_=subject.load(Path('invented-inputs'))
        self.assertEqual(frame.loc[dates[0],'entry1'],110.);self.assertAlmostEqual(frame.loc[dates[0],'r1'],100*(115/110-1));self.assertFalse(frame.confirmation_valid20.any())
    def test_spacing_equal_horizon(self):
        g=pd.DataFrame({'es_row':[0,1,4,5,9,10]});self.assertEqual(subject.spaced(g,5).es_row.tolist(),[0,5,10])
    def test_recent_requires_all_five_flags(self):
        g=subject.high_flag(pd.Series([1.,2.,3.,4.,5.,6.,7.]),3).astype(float).rolling(5,min_periods=5).max()
        self.assertTrue(pd.isna(g.iloc[5]));self.assertEqual(g.iloc[6],1.)
    def test_first_signal_run_resets(self):
        signal=pd.Series([False,True,True,False,True]);self.assertEqual((signal&~signal.shift(1,fill_value=False)).tolist(),[False,True,False,False,True])
    def test_missing_and_flat_do_not_become_positive(self):
        r=[{'date':'a',1:(0.,-.1),'matched1':0.},{'date':'b',1:(1.,.9),'matched1':0.},{'date':'c'}];v=describe(r,1);self.assertEqual(v['events'],2);self.assertEqual(v['positive_events'],1);self.assertEqual(v['mean_after_one_point_pct'],.4)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUp));assert tests.wasSuccessful()
    base=Path(__file__).resolve().parent;s=json.loads((base/'results/summary.json').read_text());rows=independent(a.input_dir);maps,masks=flags_and_signals(a.input_dir,rows);frame,checks=subject.load(a.input_dir)
    assert checks==s['checks'];assert s['source_sha256']=={k:subject.fingerprint(a.input_dir/f) for k,f in subject.FILES.items()}
    matches=0
    def compare(actual,expected):
        nonlocal matches
        assert actual.keys()==expected.keys()
        for k,v in actual.items():
            if isinstance(v,(int,float)):assert math.isclose(v,expected[k],abs_tol=1e-9,rel_tol=1e-11),(k,v,expected[k])
            else:assert v==expected[k],(k,v,expected[k])
            matches+=1
    assert [r['date'] for r in rows]==frame.index.tolist()
    for row in rows:
        for L in [20,63,252]:
            assert row['high'+str(L)]==frame.loc[row['date'],'es_high'+str(L)];matches+=1
            for key,column in [('confirm','confirmed_count'),('recent','recent_count')]:
                a_value=row[key+str(L)];b_value=frame.loc[row['date'],column+str(L)]
                assert (a_value is None and pd.isna(b_value)) or a_value==b_value;matches+=1
        for h in [1,3,5,10]:
            if h in row:assert math.isclose(row[h][0],frame.loc[row['date'],'r'+str(h)],abs_tol=1e-9);matches+=1
    aggregate=[]
    for name,chosen in masks.items():
        expected=s['results'][name];selected_dates={r['date'] for r in chosen};first=[];previous=False
        for row in rows:
            signal=row['date'] in selected_dates
            if signal and not previous:first.append(row)
            previous=signal
        assert expected['signal_dates']==len(chosen);assert expected['consecutive_signal_runs']==len(first)
        for h in [1,3,5,10]:
            available=[r for r in chosen if h in r]
            for method,events in [('all_signal_days',available),('first_consecutive_signal_day',first),('nonoverlapping',spaced(available,h)),('five_session_spacing',spaced(available,5))]:
                values=describe(events,h);compare(values,expected['horizons'][str(h)][method]);aggregate.append((name,h,method,values))
    for h in [1,3,5,10]:compare(describe(rows,h),s['baseline'][str(h)])
    for period,start,end in [('2017_2021','2017-01-01','2021-12-31'),('2022_2026','2022-01-01','2026-10-01')]:
        for group,key in [('primary','L20_mean_atleast80'),('all_20_highs','L20_all_highs')]:
            for h in [1,3,5,10]:compare(describe([r for r in masks[key] if start<=r['date']<=end],h),s['primary_periods'][period][group][str(h)])
    for L in [20,63,252]:
        dates=masks[f'L{L}_all_highs'];eligible=masks[f'L{L}_confirmation_eligible'];recent=[r for r in dates if r['recent'+str(L)] is not None];c=s['confirmation_frequency'][str(L)]
        assert c['ES_high_dates']==len(dates);assert c['same_day_eligible_highs']==len(eligible);assert c['same_day_zero_confirmation']==sum(r['confirm'+str(L)]==0 for r in eligible)
        assert c['median_series_confirming_same_day']==statistics.median(r['confirm'+str(L)] for r in eligible)
        assert c['recent_five_eligible_highs']==len(recent)
        for k in ['b5','b20','b50','b200']:compare({'confirmed_dates':sum(maps[L][k][r['date']][1] for r in recent),'denominator':len(recent),'confirmed_pct':100*sum(maps[L][k][r['date']][1] for r in recent)/len(recent)},c['recent_five_series'][k])
    # Independently audit the alternate strict-above-previous-20 definition.
    es=[]
    with (a.input_dir/subject.FILES['es']).open(encoding='utf-8-sig',newline='') as f:
        es=[(r['time'],float(r['close'])) for r in csv.DictReader(f) if r['time']<='2026-10-01']
    strict_dates={d for i,(d,c) in enumerate(es) if i>=20 and c>max(v for t,v in es[i-20:i])};strict=[r for r in rows if r['date'] in strict_dates and r['mean']>=80]
    for h in [1,3,5,10]:compare(describe(strict,h),s['high_definition_audit']['strict_above_previous20'][str(h)]);compare(describe(masks['L20_mean_atleast80'],h),s['high_definition_audit']['inclusive_current20'][str(h)])
    with (base/'results/highs_summary.csv').open() as f:csvrows=list(csv.DictReader(f))
    assert len(csvrows)==len(aggregate)==336
    for row,(name,h,method,values) in zip(csvrows,aggregate):
        assert (row['condition'],int(row['forward_ES_sessions']),row['counting_method'])==(name,h,method)
        for k,v in values.items():
            if isinstance(v,(int,float)):assert math.isclose(float(row[k]),v,abs_tol=1e-9)
            else:assert row[k]==v
    primary=s['results']['L20_mean_atleast80']['horizons'];assert primary['1']['all_signal_days']['events']==55
    assert round(primary['1']['all_signal_days']['mean_pct'],2)==-.14;assert primary['1']['all_signal_days']['positive_events']==22
    assert primary['1']['five_session_spacing']['events']==30;assert round(primary['1']['five_session_spacing']['mean_pct'],2)==-.25
    out={'passed':True,'independent_value_matches':matches,'made_up_checks':tests.testsRun,'aggregate_rows_checked':336,'source_fingerprints_match':True,'source_comparison':'The 55-event four-horizon means and 30-event next-session five-spacing claim reproduce. Annual confirmation median zero reproduces; earlier recent-confirmation percentages do not exactly reproduce under explicit full-history eligibility and today-plus-four-observation definitions.'}
    (base/'results/verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
