"""Independent CSV/date/path recount, plus invented target/entry mechanics tests."""
import argparse
import csv
from datetime import datetime,timedelta
import io
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest
import zipfile
from zoneinfo import ZoneInfo

NY=ZoneInfo('America/New_York')
FIXTURES=None


def path_result(bars,entry,target,direction,time_exit):
    hits=[i for i,b in enumerate(bars) if (b['high']>=target if direction==1 else b['low']<=target)]
    touched=bool(hits)
    gross=direction*((target if touched else time_exit)-entry)
    return touched,hits[0] if hits else None,min(direction*(target-entry),gross)


def recount(source):
    sessions={};closes={};previous=None
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')];assert len(names)==1
        with z.open(names[0]) as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle,encoding='utf-8-sig')):
                t=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
                assert previous is None or t>previous;previous=t
                assert row['is_complete'].lower()=='true'
                local=t.astimezone(NY);clock=(local.hour,local.minute)
                s=sessions.setdefault(row['session_date'],{'on':[],'entry':None,'exit':None,'rth_count':0,'degraded':False})
                s['degraded'] |= row['data_condition']=='degraded'
                if (9,30)<=clock<=(16,59):s['rth_count']+=1
                if clock>=(18,0) or clock<=(9,30) or clock==(16,59):
                    b={'time':t,'local':local,'open':float(row['open']),'high':float(row['high']),
                       'low':float(row['low']),'close':float(row['close']),'contract':row['underlying_contract'],
                       'bad':row['data_condition']=='degraded' or row['roll_transition'].lower()=='true'}
                    assert all(math.isfinite(b[k]) and b[k]>0 for k in ['open','high','low','close'])
                    assert b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']
                    if clock>=(18,0) or clock<(9,30):s['on'].append(b)
                    if clock==(18,0):assert s['entry'] is None;s['entry']=b
                    if clock==(9,30):assert s['exit'] is None;s['exit']=b
                    if clock==(16,59):assert local.date() not in closes;closes[local.date()]=b
    ordered=sorted(sessions);rows=[]
    for i,day in enumerate(ordered):
        s=sessions[day];a=s['entry'];end=s['exit']
        if a is None:continue
        assert a['local'].weekday() in [0,1,2,3,6]
        required=a['local'].date()-timedelta(days=2 if a['local'].weekday()==6 else 0)
        t=closes.get(required)
        if t is None or t['contract']!=a['contract'] or end is None:continue
        if end['time']-a['time']!=timedelta(minutes=930) or end['contract']!=a['contract']:continue
        assert end['local'].date().isoformat()==day and t['time']+timedelta(minutes=1)<=a['time']
        bars=[b for b in s['on'] if a['time']<=b['time']<end['time']]
        same=all(b['contract']==a['contract'] for b in bars)
        window=len(bars)==930 and same and not t['bad'] and not end['bad'] and not any(b['bad'] for b in bars)
        prior=sessions[ordered[i-1]] if i else {'degraded':False}
        legacy=len(bars)==930 and s['rth_count']==450 and same and not s['degraded'] and not prior['degraded']
        gap=a['open']-t['close']
        rec={'date':day,'zero':gap==0,'window_quality':window,'legacy_quality':legacy}
        if gap!=0:
            direction=1 if gap<0 else -1
            touch,first,gross=path_result(bars,a['open'],t['close'],direction,end['open'])
            delay=None
            later=[b for b in bars if b['time']>=a['time']+timedelta(minutes=1)]
            if first!=0 and later and later[0]['time']==a['time']+timedelta(minutes=1) and direction*(t['close']-later[0]['open'])>0:
                _,_,delay=path_result(later,later[0]['open'],t['close'],direction,end['open'])
            rec.update({'touch':touch,'entry_minute_touch':first==0,'gross_points':gross,'delayed_gross':delay,
                        'capped_time_exit':not touch and direction*(end['open']-a['open'])>abs(gap)})
        rows.append(rec)
    return rows


def stats(x):
    return {'events':len(x),'mean':math.fsum(x)/len(x),'median':statistics.median(x),'sum':math.fsum(x),
            'positive_events':sum(v>0 for v in x),'flat_events':sum(v==0 for v in x),
            'positive_pct':100*sum(v>0 for v in x)/len(x),'minimum':min(x),'maximum':max(x)}


class MadeUpChecks(unittest.TestCase):
    def complete_source(self,start_text,close_text,entry=99,target_price=100):
        start=datetime.fromisoformat(start_text);close=datetime.fromisoformat(close_text)
        morning=(start+timedelta(minutes=930)).astimezone(NY).date().isoformat()
        header='timestamp_utc,session_date,open,high,low,close,underlying_contract,data_condition,is_complete,roll_transition\n'
        rows=[f'{close.isoformat()},{close.astimezone(NY).date().isoformat()},{target_price},{target_price},{target_price},{target_price},ESH6,available,true,false']
        rows += [f'{(start+timedelta(minutes=i)).isoformat()},{morning},{entry},{entry+1},{entry-1},{entry},ESH6,available,true,false' for i in range(931)]
        target=Path(FIXTURES)/'complete.zip'
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(rows)))
        return target

    def bars(self):
        return [{'high':101,'low':99},{'high':106,'low':102}]

    def test_long_target_touch(self):
        self.assertEqual(path_result(self.bars(),100,105,1,103),(True,1,5))

    def test_short_target_touch(self):
        self.assertEqual(path_result([{'high':101,'low':94}],100,95,-1,102),(True,0,5))

    def test_unfilled_long_uses_morning_price(self):
        self.assertEqual(path_result([{'high':101,'low':95}],100,105,1,96),(False,None,-4))

    def test_partial_gap_recovery_can_be_positive_without_a_touch(self):
        self.assertEqual(path_result([{'high':103,'low':99}],100,105,1,102),(False,None,2))

    def test_boundary_jump_cannot_credit_more_than_target(self):
        self.assertEqual(path_result([{'high':103,'low':99}],100,105,1,108),(False,None,5))

    def test_production_path_matches_made_up_long_and_short(self):
        import pandas as pd
        from reproduce import trade
        self.assertEqual(trade(pd.DataFrame(self.bars()),100,105,1,103),(True,1,5))
        self.assertEqual(trade(pd.DataFrame([{'high':101,'low':94}]),100,95,-1,102),(True,0,5))

    def test_source_selection_checks_exact_target_and_coverage(self):
        import pandas as pd
        from reproduce import observations
        start=datetime.fromisoformat('2026-01-05T23:00:00+00:00')
        header='timestamp_utc,session_date,open,high,low,close,underlying_contract,data_condition,is_complete,roll_transition\n'
        rows=['2026-01-05T21:59:00+00:00,2026-01-05,100,100,100,100,ESH6,available,true,false']
        for i in range(931):
            t=start+timedelta(minutes=i)
            rows.append(f'{t.isoformat()},2026-01-06,99,100,98,99,ESH6,available,true,false')
        target=Path(FIXTURES)/'fixture.zip'
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(rows)))
        a,_=observations(target);b=recount(target)
        self.assertTrue(a.window_quality.iloc[0]);self.assertTrue(b[0]['window_quality'])
        self.assertTrue(a.entry_minute_touch.iloc[0]);self.assertEqual(a.gross_points.iloc[0],1)
        self.assertEqual(a.gross_points.iloc[0],b[0]['gross_points'])
        # Remove one interior minute; retain boundary prices but fail coverage.
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(rows[:10]+rows[11:])))
        a,_=observations(target);b=recount(target)
        self.assertFalse(a.window_quality.iloc[0]);self.assertFalse(b[0]['window_quality'])
        # An older Friday target must not fill in for the missing Monday close.
        changed=[r.replace('2026-01-05T21:59','2026-01-02T21:59').replace('2026-01-05,100','2026-01-02,100') if i==0 else r for i,r in enumerate(rows)]
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(changed)))
        a,_=observations(target);self.assertTrue(a.empty);self.assertEqual(recount(target),[])

    def test_flat_results_stay_in_denominator(self):
        self.assertAlmostEqual(stats([-1,0,1])['positive_pct'],100/3)

    def test_sunday_requires_friday_not_thursday(self):
        from reproduce import observations
        source=self.complete_source('2026-01-04T23:00:00+00:00','2026-01-02T21:59:00+00:00')
        a,_=observations(source);b=recount(source)
        self.assertTrue(a.window_quality.iloc[0]);self.assertTrue(b[0]['window_quality'])
        source=self.complete_source('2026-01-04T23:00:00+00:00','2026-01-01T21:59:00+00:00')
        a,_=observations(source);self.assertTrue(a.empty);self.assertEqual(recount(source),[])

    def test_zero_gap_is_counted_as_a_session_not_a_trade(self):
        from reproduce import observations
        source=self.complete_source('2026-01-05T23:00:00+00:00','2026-01-05T21:59:00+00:00',entry=100)
        a,c=observations(source);b=recount(source)
        self.assertTrue(a.zero.iloc[0]);self.assertTrue(b[0]['zero'])
        self.assertEqual(c['window_quality_sessions_including_zero'],1)
        self.assertEqual(c['zero_gaps_in_window_quality'],1)

    def test_constant_weekly_mean_range(self):
        import pandas as pd
        from reproduce import mean_range
        self.assertEqual(mean_range(pd.DataFrame({'date':['2026-01-05','2026-01-06','2026-01-12'],'gross_points':[2.,2.,2.]})),[2,2])


def main():
    global FIXTURES
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--summary',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--original-events',type=Path,help='Optional earlier saved private gap-event CSV; never exported')
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='.made-up-',dir=args.output.parent.resolve()) as folder:
        FIXTURES=folder
        tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
        if not tests.wasSuccessful():raise AssertionError('Made-up mechanics failed.')
    all_rows=recount(args.input);source=json.loads(args.summary.read_text());matches=0
    def equal(a,b):
        nonlocal matches
        assert math.isclose(a,b,rel_tol=0,abs_tol=1e-9),(a,b)
        matches+=1
    def check(rows,x):
        equal(len(rows),x['events']);equal(sum(r['touch'] for r in rows),x['touch_events'])
        equal(100*sum(r['touch'] for r in rows)/len(rows),x['touch_pct'])
        equal(sum(r['entry_minute_touch'] for r in rows),x['entry_minute_touches'])
        equal(sum(r['capped_time_exit'] for r in rows),x['capped_time_exit_cases'])
        for name,chosen in [('gross_points',rows),('touch_group',[r for r in rows if r['touch']]),('no_touch_group',[r for r in rows if not r['touch']])]:
            for key,value in stats([r['gross_points'] for r in chosen]).items():equal(value,x[name][key])
        delayed=[r['delayed_gross'] for r in rows if r['delayed_gross'] is not None]
        for name,values in [('gross_points',delayed),('net_one_point',[v-1 for v in delayed])]:
            for key,value in stats(values).items():equal(value,x['delayed_one_minute'][name][key])
        equal(len(rows)-len(delayed),x['delayed_one_minute']['skipped_events'])
    selected=[r for r in all_rows if r['window_quality'] and not r['zero']]
    legacy=[r for r in all_rows if r['legacy_quality'] and not r['zero']]
    check(selected,source['main']);check(legacy,source['full_day_quality_check'])
    for year,x in source['annual'].items():check([r for r in selected if r['date'].startswith(year)],x)
    for label,x in source['chronological_halves'].items():check([r for r in selected if (r['date']<'2025-08-29')==(label=='first_year')],x)
    for cost,x in source['costs_points'].items():
        for key,value in stats([r['gross_points']-float(cost) for r in selected]).items():equal(value,x['net'][key])
        for a,b in zip(x['net_mean_points_95'],source['main']['gross_mean_points_95']):equal(a,b-float(cost))
    equal(sum(r['window_quality'] for r in all_rows),source['checks']['window_quality_sessions_including_zero'])
    equal(sum(r['window_quality'] and r['zero'] for r in all_rows),source['checks']['zero_gaps_in_window_quality'])
    audit={'performed':False}
    if args.original_events:
        with args.original_events.open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
        old_by_day={r['session_date']:r for r in old};common=set(r['date'] for r in legacy)
        for r in legacy:
            prior=old_by_day[r['date']]
            assert r['touch']==(prior['filled_overnight'].lower()=='true')
            assert math.isclose(r['gross_points'],float(prior['pnl_overnight']),abs_tol=1e-9)
        removed=sorted(set(old_by_day)-common)
        audit={'performed':True,'old_events':len(old),'common_events':len(common),
               'excluded_older_target_dates':removed,'common_touch_and_gross_matches':2*len(common),
               'old_mean_gross_points':stats([float(r['pnl_overnight']) for r in old])['mean'],
               'current_full_day_mean_gross_points':stats([r['gross_points'] for r in legacy])['mean'],
               'note':'Exact expected calendar targets remove three older shifted-session events; remaining touch flags and gross results match. No original event file is distributed.'}
    verified={'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matches,
              'made_up_tests_passed':tests.testsRun,'eligible_main_events':len(selected),'original_event_audit':audit,
              'source_sha256':source['source_sha256'],
              'scope':'Separate CSV/date/target-path recount and descriptive aggregates. Bootstrap ranges and vendor prices are not independently audited; constant cost shifts are checked.',
              'python':'3.12.14','numpy':'2.3.5','pandas':'3.0.1','tzdata':'2026.5'}
    args.output.write_text(json.dumps(verified,indent=2)+'\n',encoding='utf-8');print(json.dumps(verified,indent=2))


if __name__=='__main__':main()
