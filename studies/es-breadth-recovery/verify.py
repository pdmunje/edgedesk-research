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
            else:
                for k in ['open','high','low']:r[k]=float(r[k])
                assert 0<=r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']<=100
        inputs[name]={r['time']:r for r in rows}
    es=[r for d,r in inputs['es'].items() if d<='2026-10-01'];common=[]
    for i,r in enumerate(es):
        if not all(r['time'] in inputs[k] for k in ['b200','b50','b20','b5']):continue
        day=datetime.fromisoformat(r['time']);out={'date':r['time'],'es_row':i,'year':day.year,'weekday':day.weekday()}
        out.update({k:inputs[k][r['time']]['close'] for k in ['b200','b50','b20','b5']})
        for h in [1,3,5,10]:
            if i+h<len(es):out[h]=(100*(es[i+h]['close']/es[i+1]['open']-1),100*(es[i+h]['close']-es[i+1]['open']-1)/es[i+1]['open'])
        
        for series in ['b200','b50']:
            candle=inputs[series][r['time']];width=candle['high']-candle['low']
            value=(candle['close']-candle['low'])/width if width else None
            out[series+'_low']=candle['low'];out[series+'_recovery']=value
            out[series+'_group']='undefined' if value is None else ('poor' if value<=.25 else 'middle' if value<.40 else 'partial' if value<.75 else 'strong')
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

class MadeUp(unittest.TestCase):
    def test_boundary_groups_and_undefined(self):
        g=subject.group_values(pd.Series([0,.25,.25001,.39999,.4,.74999,.75,1,float('nan')]))
        self.assertEqual(g.tolist(),['poor','poor','middle','middle','partial','partial','strong','strong','undefined'])
    def test_zero_range_and_full_ES_calendar(self):
        dates=['2026-01-05','2026-01-06','2026-01-07','2026-01-08']
        es=pd.DataFrame({'time':dates,'open':[100,110,120,130],'high':[106,116,126,136],'low':[99,109,119,129],'close':[105,115,125,135]})
        for w in [200,50,20,5]:es[f'S&P 500 Stocks Above {w}-Day Average · INDEX: close']=50.
        breadth=pd.DataFrame({'time':[dates[0],dates[2],dates[3]],'open':50.,'high':50.,'low':50.,'close':50.})
        def reader(path):return es.copy() if Path(path).name==subject.FILES['es'] else breadth.copy()
        with patch.object(subject.pd,'read_csv',side_effect=reader):frame,checks=subject.load(Path('invented-inputs'))
        self.assertEqual(frame.loc[dates[0],'entry1'],110.)
        self.assertAlmostEqual(frame.loc[dates[0],'r1'],100*(115/110-1))
        self.assertTrue(frame.b200_recovery.isna().all())
        self.assertEqual(checks['breadth_daily_OHLC']['b200']['zero_range_days'],3)
    def test_invalid_OHLC_rejected(self):
        es=pd.DataFrame({'time':['2026-01-01'],'open':[100.],'high':[101.],'low':[99.],'close':[100.]})
        for w in [200,50,20,5]:es[f'S&P 500 Stocks Above {w}-Day Average · INDEX: close']=50.
        bad=pd.DataFrame({'time':['2026-01-01'],'open':[50.],'high':[49.],'low':[40.],'close':[50.]})
        def reader(path):return es.copy() if Path(path).name==subject.FILES['es'] else bad.copy()
        with patch.object(subject.pd,'read_csv',side_effect=reader):
            with self.assertRaises(AssertionError):subject.load(Path('invented-inputs'))
    def test_one_group_entry_per_spell_not_per_reappearance(self):
        f=pd.DataFrame({'spell':[1,1,2,2],'es_row':[0,3,5,7]})
        self.assertEqual(subject.first_per_spell(f).es_row.tolist(),[0,5])
    def test_zero_range_keeps_underlying_spell(self):
        f=pd.DataFrame({'es_row':range(5),'b200_low':[39,39,39,41,39],'b50_low':50,'b200_group':['partial','undefined','partial','strong','partial'],'b50_group':'strong'})
        f.index=[f'2026-01-0{i+1}' for i in range(5)]
        f['b200_recovery']=[.5,float('nan'),.5,1.,.5];f['b50_recovery']=1.
        for h in [1,3,5,10]:f['r'+str(h)]=1.;f['n'+str(h)]=.9;f['matched'+str(h)]=0.
        r,_=subject.calculate(f);g=r['200_low40'];self.assertEqual(g['low_breadth_spells'],2)
        self.assertEqual(g['groups']['partial']['signal_days'],3)
        self.assertEqual(g['groups']['partial']['horizons']['10']['first_per_washout_spell']['events'],2)
    def test_spacing_equal_horizon(self):
        f=pd.DataFrame({'es_row':[0,1,5,9,10]});self.assertEqual(subject.spaced(f,5).es_row.tolist(),[0,5,10])
    def test_missing_outcome_not_zero_and_flat_not_positive(self):
        r=[{'date':'a',1:(0.,-.1),'matched1':0.},{'date':'b',1:(2.,1.9),'matched1':0.},{'date':'c'}]
        v=describe(r,1);self.assertEqual(v['events'],2);self.assertEqual(v['positive_events'],1);self.assertEqual(v['positive_pct'],50.)
    def test_one_point_round_trip(self):self.assertEqual(100*(110-100-1)/100,9.)

def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUp));assert tests.wasSuccessful()
    base=Path(__file__).resolve().parent;summary=json.loads((base/'results/summary.json').read_text());rows=independent(a.input_dir);frame,quality=subject.load(a.input_dir)
    assert summary['source_sha256']=={k:subject.fingerprint(a.input_dir/file) for k,file in subject.FILES.items()}
    assert summary['checks']==quality;assert [r['date'] for r in rows]==frame.index.tolist()
    matches=0
    def compare(actual,expected):
        nonlocal matches
        assert actual.keys()==expected.keys()
        for k,value in actual.items():
            if isinstance(value,(int,float)):assert math.isclose(value,expected[k],rel_tol=1e-11,abs_tol=1e-9),(k,value,expected[k])
            else:assert value==expected[k],(k,value,expected[k])
            matches+=1
    for r in rows:
        for series in ['b200','b50']:
            actual=frame.loc[r['date'],series+'_recovery'];expected=r[series+'_recovery']
            assert (pd.isna(actual) and expected is None) or math.isclose(actual,expected,abs_tol=1e-12)
            assert frame.loc[r['date'],series+'_group']==r[series+'_group'];matches+=2
        for h in [1,3,5,10]:
            if h in r:assert math.isclose(r[h][0],frame.loc[r['date'],'r'+str(h)],abs_tol=1e-9);matches+=1
    for h in [1,3,5,10]:compare(describe(rows,h),summary['baseline'][str(h)])
    aggregate=[]
    for label,(series,threshold) in subject.CONFIG['washouts'].items():
        previous=False;spell=0;chosen=[]
        for row in rows:
            qualifies=row[series+'_low']<=threshold
            if qualifies and not previous:spell+=1
            if qualifies:chosen.append({**row,'spell':spell})
            previous=qualifies
        result=summary['results'][label];assert result['low_breadth_spells']==spell
        assert result['low_breadth_days']==len(chosen)
        assert result['undefined_recovery_days']==sum(r[series+'_recovery'] is None for r in chosen)
        for h in [1,3,5,10]:compare(describe(chosen,h),result['all_washout_days'][str(h)])
        for group in subject.GROUPS:
            selected=[r for r in chosen if r[series+'_group']==group];d=result['groups'][group]
            assert d['signal_days']==len(selected);assert d['spells_with_this_group']==len({r['spell'] for r in selected})
            for h in [1,3,5,10]:
                valid=[r for r in selected if h in r];first=[];seen=set()
                for row in valid:
                    if row['spell'] not in seen:first.append(row);seen.add(row['spell'])
                for method,events in [('all_signal_days',valid),('first_per_washout_spell',first),('nonoverlapping',spaced(valid,h)),('five_session_spacing',spaced(valid,5))]:
                    values=describe(events,h);compare(values,d['horizons'][str(h)][method]);aggregate.append((label,group,h,method,values))
            for period,start,end in [('2017_2021','2017-01-01','2021-12-31'),('2022_2026','2022-01-01','2026-10-01')]:
                for h in [1,3,5,10]:compare(describe([r for r in selected if start<=r['date']<=end],h),summary['periods'][label][period][group][str(h)])
    with (base/'results/recovery_summary.csv').open() as f:csvrows=list(csv.DictReader(f))
    assert len(csvrows)==len(aggregate)==192
    for row,(label,group,h,method,values) in zip(csvrows,aggregate):
        assert (row['washout'],row['recovery_group'],int(row['forward_ES_sessions']),row['counting_method'])==(label,group,h,method)
        for k,v in values.items():
            if isinstance(v,(int,float)):assert math.isclose(float(row[k]),v,abs_tol=1e-9)
            else:assert row[k]==v
    report={'passed':True,'made_up_checks':tests.testsRun,'independent_value_matches':matches,'aggregate_rows_checked':len(aggregate),'all_source_fingerprints_match':True,'source_claim_comparison':'Primary recovery counts/rounded means and 200-day five-spacing means reproduce. 50-day partial 10-session five-spacing mean is 2.50%, not the earlier narrative 2.51%; no old code is available to resolve that difference.'}
    (base/'results/verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
