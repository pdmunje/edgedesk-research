"""Separate csv/date/statistics recount and clearly invented boundary cases."""
import argparse,csv,json,math,statistics,unittest
from datetime import date,timedelta
from pathlib import Path
import pandas as pd
import reproduce as subject
def week(d):return d-timedelta(days=d.weekday())
def spaced(entries,h):
    out=[]
    for e in entries:
        if not out or e-out[-1]>=h:out.append(e)
    return out
def load(folder):
    raw={}
    for key,file in subject.FILES.items():
        with (folder/file).open(encoding='utf-8-sig',newline='') as f:source=list(csv.DictReader(f))
        raw[key]=[{'date':date.fromisoformat(r['time']),**{k:float(r[k]) for k in ['open','high','low','close']}} for r in source]
    es=[r for r in raw['es'] if r['date']<=date(2026,10,1)];bydate={r['date']:i for i,r in enumerate(es)}
    for i,r in enumerate(es):
        r['year']=r['date'].year;r['weekday']=r['date'].weekday();r['oc']=100*(r['close']/r['open']-1);r['range']=100*(r['high']-r['low'])/r['open']
        if i:r['cc']=100*(r['close']/es[i-1]['close']-1);r['gap']=100*(r['open']/es[i-1]['close']-1)
    common=set(bydate)
    for key in ['b200','b50','b20','b5']:common&={r['date'] for r in raw[key]}
    signals={}
    for key,name,cutoff in [('b200','breadth200_partial',40),('b50','breadth50_partial',30)]:
        entries=[]
        for r in raw[key]:
            if r['date'] not in common or r['high']==r['low']:continue
            recovery=(r['close']-r['low'])/(r['high']-r['low'])
            if r['low']<=cutoff and .4<=recovery<.75:entries.append(bydate[r['date']]+1)
        signals[name]=entries
    changes={week(r['date']):r['close']-r['open'] for r in raw['skew'] if week(r['date'])<=date(2026,9,21)};ws=sorted(changes);first_es={}
    for i,r in enumerate(es):first_es.setdefault(week(r['date']),i)
    for name in ['skew_drop5','skew_normalized_calendar','skew_normalized_reported']:signals[name]=[]
    for k,w in enumerate(ws):
        entry=first_es.get(w+timedelta(weeks=1))
        if entry is None:continue
        if changes[w]<=-5:signals['skew_drop5'].append(entry)
        old=[changes.get(w-timedelta(weeks=j)) for j in range(104,0,-1)]
        reported=[changes[x] for x in ws[k-104:k]] if k>=104 else []
        for name,history in [('skew_normalized_calendar',old),('skew_normalized_reported',reported)]:
            if len(history)==104 and None not in history and statistics.stdev(history)>0:
                z=(changes[w]-statistics.mean(history))/statistics.stdev(history)
                if z<=-1.5:signals[name].append(entry)
    return es,signals
def metric(values,weights):
    total=math.fsum(weights);positive=[(x,w) for x,w in zip(values,weights) if x>0];negative=[(x,w) for x,w in zip(values,weights) if x<0];zeros=[w for x,w in zip(values,weights) if x==0];up=math.fsum(w for x,w in positive);down=math.fsum(w for x,w in negative);zero=math.fsum(zeros)
    return {'day_weight':total,'positive_day_weight':up,'negative_day_weight':down,'zero_day_weight':zero,'positive_pct':100*up/total,'negative_pct':100*down/total,'zero_pct':100*zero/total,'mean_pct':math.fsum(x*w for x,w in zip(values,weights))/total,'mean_positive_pct':math.fsum(x*w for x,w in positive)/up if up else None,'mean_negative_pct':math.fsum(x*w for x,w in negative)/down if down else None}
def refs(es,e,h):return spaced([j for j in range(1,len(es)-h+1) if es[j]['year']==es[e]['year'] and es[j]['weekday']==es[e]['weekday'] and (j+h<=e or j>=e+h)],h)
def summarize(es,entries,h):
    references={e:refs(es,e,h) for e in entries};chosen=[e for e in entries if references[e]];actual=[i for e in chosen for i in range(e,e+h)];ri=[];weights=[]
    for e in chosen:
        for r in references[e]:ri.extend(range(r,r+h));weights.extend([1/len(references[e])]*h)
    out={'events':len(entries),'matched_events':len(chosen),'unmatched_events':len(entries)-len(chosen),'event_days':len(actual),'unique_event_days':len(set(actual)),'first_entry_date':es[min(chosen)]['date'].isoformat(),'last_entry_date':es[max(chosen)]['date'].isoformat(),'last_outcome_date':es[max(chosen)+h-1]['date'].isoformat(),'minimum_reference_windows':min(len(references[e]) for e in chosen),'median_reference_windows':statistics.median(len(references[e]) for e in chosen),'reference_window_appearances':sum(len(references[e]) for e in chosen),'reference_day_appearances':len(ri),'unique_reference_days':len(set(ri))}
    out['measures']={name:{'signal':metric([es[i][key] for i in actual],[1]*len(actual)),'reference':metric([es[i][key] for i in ri],weights)} for name,key in [('close_to_close','cc'),('open_to_close','oc'),('prior_close_to_open','gap')]}
    window=[100*(es[e+h-1]['close']/es[e]['open']-1) for e in chosen];refwindow=[statistics.mean(100*(es[r+h-1]['close']/es[r]['open']-1) for r in references[e]) for e in chosen]
    out.update(mean_range_pct=statistics.mean(es[i]['range'] for i in actual),reference_mean_range_pct=math.fsum(es[i]['range']*w for i,w in zip(ri,weights))/math.fsum(weights),mean_window_change_pct=statistics.mean(window),positive_windows=sum(x>0 for x in window),positive_windows_pct=100*sum(x>0 for x in window)/len(window),reference_mean_window_change_pct=statistics.mean(refwindow))
    path=[]
    for d in range(1,h+1):
        cumulative=[100*(es[e+d-1]['close']/es[e]['open']-1) for e in chosen];rr=[statistics.mean(100*(es[r+d-1]['close']/es[r]['open']-1) for r in references[e]) for e in chosen];refoc=[statistics.mean(es[r+d-1]['oc'] for r in references[e]) for e in chosen];refup=[statistics.mean(es[r+d-1]['cc']>0 for r in references[e]) for e in chosen];pos=sum(es[e+d-1]['cc']>0 for e in chosen)
        path.append({'session_number':d,'windows':len(chosen),'mean_cumulative_pct':statistics.mean(cumulative),'reference_mean_cumulative_pct':statistics.mean(rr),'mean_session_open_to_close_pct':statistics.mean(es[e+d-1]['oc'] for e in chosen),'positive_close_to_close_days':pos,'positive_close_to_close_pct':100*pos/len(chosen),'reference_positive_close_to_close_pct':100*statistics.mean(refup),'reference_mean_session_open_to_close_pct':statistics.mean(refoc)})
    return out,path
class Examples(unittest.TestCase):
    def test_recovery_boundaries(self):
        self.assertTrue(.4<=(38-30)/(50-30)<.75);self.assertFalse(.4<=(45-30)/(50-30)<.75)
    def test_nonoverlap_includes_exact_boundary(self):self.assertEqual(subject.spaced([1,2,10,11,21],10),[1,11,21])
    def test_current_excluded_from_normalization(self):
        old=[-1,1]*52;z=subject.standardized(pd.Series(old+[-2]));self.assertAlmostEqual(z.iloc[-1],-2/statistics.stdev(old))
    def test_missing_week_invalidates_calendar_history(self):self.assertTrue(pd.isna(subject.standardized(pd.Series([1,-1]*51+[None,1,-2])).iloc[-1]))
    def test_flat_days_and_own_denominators(self):
        r=subject.measure([2,-1,0],[1,1,1]);self.assertEqual(r['positive_day_weight'],1);self.assertEqual(r['zero_day_weight'],1);self.assertEqual(r['mean_positive_pct'],2);self.assertAlmostEqual(r['mean_pct'],1/3)
    def test_reference_equal_event_weight(self):
        # First event has one reference day, second has two; each event totals weight one.
        r=subject.measure([1,2,4],[1,.5,.5]);self.assertEqual(r['day_weight'],2);self.assertEqual(r['mean_pct'],2)
    def test_reference_excludes_shared_held_days(self):
        es=pd.DataFrame({'row':range(20),'year':[2026]*20,'weekday':[0]*20});self.assertEqual(subject.references(es,5,4),[1,9,13])
    def test_daily_gaps_and_entries_differ(self):
        prior=100;opening=110;closing=111;cc=100*(closing/prior-1);oc=100*(closing/opening-1);self.assertAlmostEqual(cc,11);self.assertAlmostEqual(oc,100/110)
    def test_compound_not_sum(self):self.assertNotAlmostEqual(100*(1.1*.9-1),10-10)
    def test_holiday_week(self):self.assertEqual(week(date(2026,9,8)),date(2026,9,7))
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);a=p.parse_args();saved=json.loads((subject.HERE/'results/summary.json').read_text());es,signals=load(a.input_dir);frame,original,checks=subject.prepare(a.input_dir);assert signals==original;count=0
    def compare(a,b):
        nonlocal count
        if isinstance(a,dict):
            assert a.keys()==b.keys(),(a.keys(),b.keys())
            for k in a:compare(a[k],b[k])
        elif isinstance(a,list):
            assert len(a)==len(b)
            for x,y in zip(a,b):compare(x,y)
        elif isinstance(a,(float,int)):assert math.isclose(a,b,rel_tol=2e-10,abs_tol=2e-9),(a,b);count+=1
        else:assert a==b,(a,b);count+=1
    for condition,entries in signals.items():
        h=saved['results'][condition]['horizon_sessions'];valid=sorted(set(i for i in entries if i>=1 and i+h<=len(es)));assert len(valid)==saved['results'][condition]['complete_signal_windows']
        for method,chosen in [('nonoverlapping_primary',spaced(valid,h)),('all_signals_audit',valid)]:
            s,path=summarize(es,chosen,h);compare({'summary':s,'daily_path':path},saved['results'][condition]['methods'][method])
            if method=='nonoverlapping_primary':assert s['unique_event_days']==s['event_days']
            for values in s['measures'].values():
                for m in values.values():
                    reconstructed=(m['positive_pct']/100)*(m['mean_positive_pct'] or 0)+(m['negative_pct']/100)*(m['mean_negative_pct'] or 0);assert math.isclose(reconstructed,m['mean_pct'],abs_tol=1e-12)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Examples));assert result.wasSuccessful()
    assert saved['source_sha256']=={k:subject.fingerprint(a.input_dir/v) for k,v in subject.FILES.items()}
    out={'independent_numeric_or_date_comparisons':count,'invented_boundary_tests':result.testsRun,'exact_signal_entries_match':True,'no_repeated_held_sessions_in_each_primary_condition':True,'daily_frequency_size_identity_verified':True,'source_fingerprints_verified':True,'passed':True};(subject.HERE/'results/verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
