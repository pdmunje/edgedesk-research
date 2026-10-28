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

class MadeUp(unittest.TestCase):
    def test_next_open_keeps_ES_date_without_breadth(self):
        dates=['2026-01-05','2026-01-06','2026-01-07','2026-01-08']
        es=pd.DataFrame({'time':dates,'open':[100,110,120,130],'high':[106,116,126,136],'low':[99,109,119,129],'close':[105,115,125,135]})
        for w in [200,50,20,5]:es[f'S&P 500 Stocks Above {w}-Day Average · INDEX: close']=50.
        breadth=pd.DataFrame({'time':[dates[0],dates[2],dates[3]],'open':50.,'high':50.,'low':50.,'close':50.})
        def reader(path):return es.copy() if Path(path).name==subject.FILES['es'] else breadth.copy()
        with patch.object(subject.pd,'read_csv',side_effect=reader):frame,_=subject.load(Path('invented-inputs'))
        self.assertEqual(frame.loc[dates[0],'entry1'],110.)
        self.assertAlmostEqual(frame.loc[dates[0],'r1'],100*(115/110-1))
    def test_one_point_cost_percent(self):self.assertAlmostEqual(100*(110-100-1)/100,9.)
    def test_nonoverlap_equal_horizon_allowed(self):
        r=[{'es_row':i} for i in [0,1,4,5,9,10]];self.assertEqual([x['es_row'] for x in spaced(r,5)],[0,5,10])
    def test_subject_spacing(self):
        g=pd.DataFrame({'es_row':[0,1,4,5,9,10]});self.assertEqual(subject.spaced(g,5).es_row.tolist(),[0,5,10])
    def test_one_session_spacing_keeps_every_day(self):self.assertEqual(len(spaced([{'es_row':0},{'es_row':1}],1)),2)
    def test_missing_outcome_not_zero(self):
        r=[{'date':'2026-01-01',1:(2.,1.),'matched1':0.},{'date':'2026-01-02'}];self.assertEqual(describe(r,1)['events'],1)
    def test_episode_first_day_and_threshold_boundary(self):
        index=pd.date_range('2026-01-01',periods=7);g=pd.DataFrame({'es_row':range(7),'b200':[31,30,29,31,30,31,31],'b50':50},index=index)
        g.index=g.index.strftime('%Y-%m-%d')
        for h in [1,3,5,10]:g['r'+str(h)]=1.;g['n'+str(h)]=.9;g['matched'+str(h)]=0.
        r=subject.calculate(g)['b200']['30'];self.assertEqual(r['qualifying_days'],3);self.assertEqual(r['consecutive_signal_runs'],2)
        self.assertEqual(r['horizons']['10']['first_day_of_run']['events'],2)
    def test_positive_means_strictly_above_zero(self):
        rows=[{'date':str(i),1:(v,v),'matched1':0.} for i,v in enumerate([-1.,0.,1.])];self.assertEqual(describe(rows,1)['positive_events'],1)
    def test_leave_one_out(self):
        values=[1,2,9];self.assertEqual((sum(values)-9)/(len(values)-1),1.5)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-dir',required=True,type=Path);p.add_argument('--summary',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUp));assert tests.wasSuccessful()
    before={k:subject.fingerprint(a.input_dir/f) for k,f in subject.FILES.items()};s=json.loads(a.summary.read_text());assert before==s['source_sha256']
    rows=independent(a.input_dir);frame,checks=subject.load(a.input_dir);assert [r['date'] for r in rows]==frame.index.tolist()
    matches=0
    def compare(actual,expected):
        nonlocal matches
        for k,value in actual.items():
            if isinstance(value,(int,float)):assert math.isclose(value,expected[k],rel_tol=1e-11,abs_tol=1e-9),(k,value,expected[k])
            else:assert value==expected[k]
            matches+=1
    for h in [1,3,5,10]:
        compare(describe(rows,h),s['baseline'][str(h)])
        for r in rows:
            if h in r:
                assert math.isclose(r[h][0],frame.loc[r['date'],'r'+str(h)],rel_tol=1e-12,abs_tol=1e-9)
                matches+=1
    for series in ['b200','b50']:
        for threshold in [10,20,30,40]:
            chosen=[r for r in rows if r[series]<=threshold]
            starts=[r for i,r in enumerate(rows) if r[series]<=threshold and (i==0 or rows[i-1][series]>threshold)]
            expected=s['results'][series][str(threshold)];assert len(chosen)==expected['qualifying_days'] and len(starts)==expected['consecutive_signal_runs']
            for h in [1,3,5,10]:
                available=[r for r in chosen if h in r]
                for name,group in [('all_signal_days',available),('first_day_of_run',starts),('nonoverlapping',spaced(available,h)),('five_session_spacing',spaced(available,5))]:compare(describe(group,h),expected['horizons'][str(h)][name])
    for label,test in [('2017_2021',lambda r:r['date']<'2022-01-01'),('2022_2026',lambda r:r['date']>='2022-01-01')]:
        for h in [1,3,5,10]:compare(describe([r for r in rows if r['b200']<=30 and test(r)],h),s['primary_periods'][label][str(h)])
    primary=s['results']['b200']['30'];assert primary['qualifying_days']==166
    prior_means={1:.27,3:.74,5:1.24,10:2.66}
    for h,mean in prior_means.items():assert abs(primary['horizons'][str(h)]['all_signal_days']['mean_pct']-mean)<.005
    old_spacing=primary['horizons']['10']['five_session_spacing'];assert old_spacing['events']==40 and abs(old_spacing['mean_pct']-2.35)<.005
    assert before=={k:subject.fingerprint(a.input_dir/f) for k,f in subject.FILES.items()}
    result={'passed':True,'checked_date':'2026-10-16','source_sha256':before,'independent_value_matches':matches,'made_up_tests_passed':tests.testsRun,
            'common_signal_dates':len(rows),'threshold_horizon_method_rows':128,
            'prior_claim_check':'166 signals, all four rounded horizon means, and the 40-observation five-spacing ten-session mean reproduce the earlier source narrative. Raw old calculation files were not recovered; this is a fresh implementation checked independently.',
            'scope':'Independent CSV/date/forward-price/leave-one-out and episode/spacing arithmetic; all 128 result rows, periods and individual forward returns checked. No vendor-constituent, publication-timestamp, contract-roll or order-execution audit.'}
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
