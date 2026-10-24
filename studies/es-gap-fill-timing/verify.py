"""Separate stdlib CSV/time recount and made-up boundary/quality tests."""
import argparse
import csv
from datetime import datetime,timedelta
import io
import json
import math
from pathlib import Path
import unittest
import zipfile
from zoneinfo import ZoneInfo
import pandas as pd
import reproduce as subject

NY=ZoneInfo('America/New_York')

def independent(source):
    sessions={};closes={};previous_time=None
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        for r in csv.DictReader(io.TextIOWrapper(z.open(names[0]),encoding='utf-8-sig')):
            t=datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00'));local=t.astimezone(NY)
            assert previous_time is None or t>previous_time;previous_time=t
            assert r['is_complete'].lower()=='true'
            b=(t,float(r['open']),float(r['high']),float(r['low']),float(r['close']),r['underlying_contract'],r['data_condition']=='degraded' or r['roll_transition'].lower()=='true')
            assert all(math.isfinite(x) and x>0 for x in b[1:5]) and b[3]<=min(b[1],b[4])<=max(b[1],b[4])<=b[2]
            g=sessions.setdefault(r['session_date'],{'bars':[],'entry':None,'close':None,'degraded':False})
            g['bars'].append(b);g['degraded'] |= r['data_condition']=='degraded'
            if (local.hour,local.minute)==(18,0):assert g['entry'] is None;g['entry']=b
            if (local.hour,local.minute)==(16,59):
                assert local.date() not in closes;closes[local.date()]=b;g['close']=b
    main=[];old=[];on_only=[];previous_session=None
    ex=dict.fromkeys(['missing_required_close','target_contract_change','missing_or_misaligned_full_day','flagged_or_mixed_contract_full_day','zero_gap'],0)
    candidates=0
    def hit(path,target,gap,start):
        for b in path:
            if (b[3]<=target if gap>0 else b[2]>=target):return int((b[0]-start).total_seconds()/60)
        return None
    for day,g in sorted(sessions.items()):
        prior=previous_session;previous_session=g;a=g['entry']
        if a is None:continue
        candidates+=1;start=a[0];local=start.astimezone(NY)
        path=[b for b in g['bars'] if start<=b[0]<start+timedelta(minutes=1380)]
        on=[b for b in path if b[0]<start+timedelta(minutes=930)]
        if prior and prior['close']:
            target=prior['close'];gap=a[1]-target[4]
            if (gap and target[5]==a[5] and len(on)==930 and len(path)==1380 and all(b[5]==a[5] for b in on)
                and not prior['degraded'] and not g['degraded']):
                old.append({'date':day,'gap':gap,'minute':hit(path,target[4],gap,start)})
        target=closes.get(local.date()-timedelta(days=2 if local.weekday()==6 else 0))
        if target is None:ex['missing_required_close']+=1;continue
        if target[5]!=a[5]:ex['target_contract_change']+=1;continue
        gap=a[1]-target[4];record={'date':day,'gap':gap,'minute':hit(path,target[4],gap,start) if gap else None}
        exits=[b for b in path if b[0]==start+timedelta(minutes=930)]
        if (gap and len(on)==930 and all(b[5]==a[5] and not b[6] for b in on) and not target[6]
            and len(exits)==1 and not exits[0][6] and exits[0][5]==a[5]):
            on_only.append(dict(record,minute=hit(on,target[4],gap,start)))
        if len(path)!=1380 or any(b[0]!=start+timedelta(minutes=i) for i,b in enumerate(path)):
            ex['missing_or_misaligned_full_day']+=1;continue
        if target[6] or any(b[6] or b[5]!=a[5] for b in path):ex['flagged_or_mixed_contract_full_day']+=1;continue
        if not gap:ex['zero_gap']+=1;continue
        main.append(record)
    return main,old,on_only,ex,candidates

def check_summary(rows,saved):
    matches=0
    def eq(a,b):
        nonlocal matches
        if a is None or b is None:assert a is b
        else:assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10),(a,b)
        matches+=1
    times=[r['minute'] for r in rows];n=len(times);on=sum(t is not None and t<930 for t in times)
    eq(n,saved['events']);eq(on,saved['overnight_touches'])
    for r in saved['cumulative']:
        count=sum(t is not None and t<r['before_minute'] for t in times)
        eq(count,r['touches']);eq(100*count/n if n else None,r['pct_all_gaps'])
        eq(100*count/on if on and r['before_minute']<=930 else None,r['pct_overnight_touches'])
    if 'exclusive_buckets' in saved:
        total=0
        for r in saved['exclusive_buckets']:
            count=sum(t is not None and r['from_minute']<=t<r['before_minute'] for t in times);total+=count;eq(count,r['events'])
        eq(sum(t is None for t in times),saved['no_touch_before_1700']);eq(total+saved['no_touch_before_1700'],n)
    for r in saved['conditional']:
        m=r['still_open_at_minute'];remaining=[t for t in times if t is None or t>=m];later=sum(t is not None and t<930 for t in remaining)
        eq(len(remaining),r['still_open']);eq(later,r['later_overnight_touches']);eq(100*later/len(remaining) if remaining else None,r['pct_remaining'])
    return matches

def fixture(drop=None,flag=None,contract=None,zero=False,missing_target=False):
    start=datetime(2026,1,5,18,tzinfo=NY);records=[]
    def bar(t,price=101.,bad=False,c='ESH6'):
        return dict(timestamp_utc=t.astimezone(ZoneInfo('UTC')).isoformat(),session_date='2026-01-06',open=price,high=price,low=price,close=price,underlying_contract=c,data_condition='degraded' if bad else 'ok',is_complete=True,roll_transition=False)
    target=bar(start.replace(hour=16,minute=59),101. if zero else 100.)
    target['session_date']='2026-01-05'
    if not missing_target:records.append(target)
    for i in range(1380):
        if i==drop:continue
        r=bar(start+timedelta(minutes=i),bad=i==flag,c='ESM6' if i==contract else 'ESH6')
        if i==30:r['low']=100.
        records.append(r)
    archive=io.BytesIO();buffer=io.StringIO();w=csv.DictWriter(buffer,fieldnames=records[-1].keys());w.writeheader();w.writerows(records)
    with zipfile.ZipFile(archive,'w') as z:z.writestr('fixture.csv',buffer.getvalue())
    archive.seek(0)
    return subject.calculate(archive)

class MadeUpTests(unittest.TestCase):
    def test_up_gap_touch(self):self.assertEqual(subject.first_touch(pd.DataFrame({'low':[101,100],'high':[102,102]}),100,2),1)
    def test_down_gap_touch(self):self.assertEqual(subject.first_touch(pd.DataFrame({'low':[98,98],'high':[99,100]}),100,-2),1)
    def test_no_touch(self):self.assertIsNone(subject.first_touch(pd.DataFrame({'low':[101],'high':[102]}),100,2))
    def test_first_minute(self):self.assertEqual(subject.first_touch(pd.DataFrame({'low':[100],'high':[102]}),100,2),0)
    def test_cutoff_excludes_exact_start(self):
        s=subject.summarize([{'minute':29},{'minute':30},{'minute':930},{'minute':None}]);r=next(x for x in s['cumulative'] if x['before_minute']==30)
        self.assertEqual(r['touches'],1);self.assertEqual(s['overnight_touches'],2)
    def test_full_path(self):self.assertEqual(fixture()[0][0]['minute'],30)
    def test_missing_daytime_cannot_be_nonfill(self):self.assertEqual(len(fixture(drop=1000)[0]),0)
    def test_flagged_daytime_excluded(self):self.assertEqual(len(fixture(flag=1000)[0]),0)
    def test_daytime_contract_change_excluded(self):self.assertEqual(len(fixture(contract=1000)[0]),0)
    def test_zero_gap_excluded(self):self.assertEqual(fixture(zero=True)[3]['sequential_exclusions']['zero_gap'],1)
    def test_missing_calendar_target_excluded(self):self.assertEqual(fixture(missing_target=True)[3]['sequential_exclusions']['missing_required_close'],1)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True,type=Path);p.add_argument('--summary',required=True,type=Path)
    p.add_argument('--original-events',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpTests));assert tests.wasSuccessful()
    saved=json.loads(a.summary.read_text());before=subject.fingerprint(a.input);assert before==saved['source_sha256']
    rows,old,on,ex,candidates=independent(a.input);matches=0
    matches+=check_summary(rows,saved['main']);matches+=check_summary(old,saved['original_observed_target_sample']);matches+=check_summary(on,saved['overnight_only_comparator'])
    filters={'sunday_reopen':lambda r:datetime.fromisoformat(r['date']).weekday()==0,'other_weekday_reopens':lambda r:datetime.fromisoformat(r['date']).weekday()!=0,
        'gap_under_one_point':lambda r:abs(r['gap'])<1,'gap_one_to_under_three':lambda r:1<=abs(r['gap'])<3,
        'gap_three_to_under_ten':lambda r:3<=abs(r['gap'])<10,'gap_ten_or_more':lambda r:abs(r['gap'])>=10,
        'first_year':lambda r:r['date']<'2025-08-29','second_year':lambda r:r['date']>='2025-08-29'}
    for name,f in filters.items():matches+=check_summary([r for r in rows if f(r)],saved['groups'][name])
    assert ex==saved['checks']['sequential_exclusions'] and candidates==saved['checks']['evening_candidates']
    assert sorted(set(r['date'] for r in old)-set(r['date'] for r in rows))==saved['checks']['old_events_absent_from_main']
    for m in [5,60]:assert sum(r['minute'] is not None and r['minute']<=m for r in old)==saved['checks']['old_inclusive_cutoff_counts'][str(m)]
    for actual,expected in zip([rows,old,on],subject.calculate(a.input)[:3]):assert actual==expected
    assert len(set(r['date'] for r in rows)&set(r['date'] for r in old))==saved['overlap']['main_shared_with_original']
    assert len(set(r['date'] for r in rows)&set(r['date'] for r in on))==saved['overlap']['main_shared_with_400_overnight']
    audit={'performed':False}
    if a.original_events:
        with a.original_events.open(encoding='utf-8-sig',newline='') as f:prior={r['session_date']:r for r in csv.DictReader(f)}
        assert set(prior)==set(r['date'] for r in old)
        for r in old:
            t=prior[r['date']]['fill_minutes'];assert r['minute']==(int(float(t)) if t else None)
            assert r['gap']==float(prior[r['date']]['gap'])
        audit={'performed':True,'saved_events':len(prior),'fresh_gap_and_first_touch_matches':2*len(prior),
            'note':'All original saved event dates, gap sizes and first-touch minute offsets reproduced. Private event file is not distributed.'}
    assert subject.fingerprint(a.input)==before
    out={'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matches,'made_up_tests_passed':tests.testsRun,
        'source_sha256':before,'main_events':len(rows),'original_event_audit':audit,
        'scope':'Separate standard-library CSV/time/price-path parser; every event date, gap and first-touch offset matched the pandas calculation; aggregate counts and percentages checked. No vendor or order-execution audit.'}
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))

if __name__=='__main__':main()
