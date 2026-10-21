"""Separate CSV/timestamp recount and made-up hour/timing checks."""
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


def recount(source):
    cuts={};minute_counts={};bad={};contracts={}
    previous=None
    with zipfile.ZipFile(source) as z:
        names=[n for n in z.namelist() if n.lower().endswith('.csv')]
        assert len(names)==1
        with z.open(names[0]) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream,encoding='utf-8-sig')):
                t=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
                assert previous is None or t>previous
                previous=t
                assert row['is_complete'].lower()=='true'
                local=t.astimezone(NY);clock=(local.hour,local.minute);day=row['session_date']
                price=float(row['open']);assert math.isfinite(price) and price>0
                if (2,0)<=clock<(3,0):minute_counts[day]=minute_counts.get(day,0)+1
                if (2,0)<=clock<=(3,0):
                    bad[day]=bad.get(day,False) or row['data_condition']=='degraded' or row['roll_transition'].lower()=='true'
                    contracts.setdefault(day,set()).add(row['underlying_contract'])
                if clock in [(2,0),(3,0),(18,0),(9,30)]:
                    key=(day,clock);assert key not in cuts
                    cuts[key]={'time':t,'local':local,'price':price,'contract':row['underlying_contract']}
    rows=[]
    for (day,clock),a in cuts.items():
        if clock!=(2,0):continue
        b=cuts.get((day,(3,0)))
        if b is None or b['time']-a['time']!=timedelta(hours=1) or b['contract']!=a['contract']:continue
        assert a['local'].date().isoformat()==b['local'].date().isoformat()==day
        assert a['local'].weekday()<5
        start=cuts.get((day,(18,0)));end=cuts.get((day,(9,30)))
        shared=bool(start and end and start['contract']==end['contract']==a['contract'] and
                    end['time']-start['time']==timedelta(minutes=930) and start['time']<a['time']<b['time']<end['time'])
        points=b['price']-a['price']
        row={'date':day,'points':points,'bps':points/a['price']*10000,'shared':shared,
             'strict':minute_counts.get(day,0)==60 and not bad.get(day,True) and len(contracts.get(day,set()))==1}
        if shared:
            row['overnight_points']=end['price']-start['price'];row['overnight_bps']=row['overnight_points']/start['price']*10000
        rows.append(row)
    return sorted(rows,key=lambda r:r['date'])


def stats(x):
    return {'hours':len(x),'mean':math.fsum(x)/len(x),'median':statistics.median(x),
            'positive_hours':sum(v>0 for v in x),'flat_hours':sum(v==0 for v in x),
            'positive_pct':100*sum(v>0 for v in x)/len(x),'minimum':min(x),'maximum':max(x)}


class MadeUpChecks(unittest.TestCase):
    def source(self,rows):
        target=Path(FIXTURES)/'fixture.zip'
        header='timestamp_utc,session_date,open,underlying_contract,data_condition,is_complete,roll_transition\n'
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(rows)))
        return target

    def both(self,rows):
        from reproduce import observations
        source=self.source(rows);a,c=observations(source);b=recount(source)
        self.assertEqual(len(a),len(b));return a,b,c

    def winter(self):
        return ['2026-01-05T07:00:00Z,2026-01-05,5000,ESH6,available,true,false',
                '2026-01-05T08:00:00Z,2026-01-05,5001,ESH6,available,true,false']

    def test_winter_hour_uses_07_08_utc(self):
        a,b,_=self.both(self.winter());self.assertEqual(a.points.iloc[0],1);self.assertEqual(b[0]['points'],1)

    def test_summer_hour_uses_06_07_utc(self):
        a,_,c=self.both(['2026-07-06T06:00:00Z,2026-07-06,5000,ESU6,available,true,false',
                         '2026-07-06T07:00:00Z,2026-07-06,5002,ESU6,available,true,false'])
        self.assertEqual(a.points.iloc[0],2);self.assertEqual(c['utc_entry_hour_counts'],{'6':1})

    def test_spring_clock_jump_does_not_create_a_02_entry(self):
        a,_,c=self.both(['2026-03-08T07:00:00Z,2026-03-08,5000,ESH6,available,true,false'])
        self.assertTrue(a.empty);self.assertEqual(c['02_entry_candidates'],0)

    def test_missing_03_is_not_filled(self):
        a,_,c=self.both(self.winter()[:1]);self.assertTrue(a.empty);self.assertEqual(c['excluded']['missing_03'],['2026-01-05'])

    def test_different_contract_is_excluded(self):
        rows=self.winter();rows[1]=rows[1].replace('ESH6','ESM6')
        a,_,_=self.both(rows);self.assertTrue(a.empty)

    def test_hour_does_not_require_overnight_boundaries(self):
        a,b,_=self.both(self.winter());self.assertEqual(len(a),1);self.assertFalse(b[0]['shared'])

    def test_missing_middle_minutes_only_exclude_strict_subset(self):
        a,b,_=self.both(self.winter());self.assertFalse(a.strict.iloc[0]);self.assertFalse(b[0]['strict'])

    def test_complete_60_minutes_plus_exit_pass_strict(self):
        start=datetime.fromisoformat('2026-01-05T07:00:00+00:00')
        rows=[f'{(start+timedelta(minutes=i)).isoformat()},2026-01-05,{5000+i/4},ESH6,available,true,false' for i in range(61)]
        a,b,_=self.both(rows);self.assertTrue(a.strict.iloc[0]);self.assertTrue(b[0]['strict'])

    def test_quality_flag_excludes_only_strict_subset(self):
        start=datetime.fromisoformat('2026-01-05T07:00:00+00:00')
        rows=[f'{(start+timedelta(minutes=i)).isoformat()},2026-01-05,{5000+i/4},ESH6,available,true,false' for i in range(61)]
        rows[30]=rows[30].replace('available','degraded')
        a,b,_=self.both(rows);self.assertEqual(len(a),1);self.assertFalse(a.strict.iloc[0]);self.assertFalse(b[0]['strict'])

    def test_wrong_elapsed_time_is_excluded(self):
        rows=self.winter();rows[1]=rows[1].replace('2026-01-05T','2026-01-06T')
        a,_,c=self.both(rows);self.assertTrue(a.empty);self.assertEqual(c['excluded']['wrong_elapsed_time'],['2026-01-05'])

    def test_flat_hour_remains_in_denominator(self):
        self.assertAlmostEqual(stats([-1,0,1])['positive_pct'],100/3)

    def test_constant_weekly_sample_has_constant_mean_range(self):
        import pandas as pd
        from reproduce import mean_ranges
        frame=pd.DataFrame({'date':['2026-01-05','2026-01-06','2026-01-12'],'points':[2.,2.,2.],'bps':[4.,4.,4.]})
        self.assertEqual(mean_ranges(frame),{'points_mean_95':[2,2],'bps_mean_95':[4,4]})


def main():
    global FIXTURES
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--summary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path,help='Optional saved original overnight-study aggregate JSON')
    args=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='.made-up-',dir=args.output.parent.resolve()) as folder:
        FIXTURES=folder
        test=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
        if not test.wasSuccessful():raise AssertionError('Made-up checks failed.')
    actual=recount(args.input);summary=json.loads(args.summary.read_text())
    matches=0
    def equal(a,b):
        nonlocal matches
        assert math.isclose(a,b,rel_tol=0,abs_tol=1e-9),(a,b)
        matches+=1
    def check(rows,expected):
        for unit in ['points','bps']:
            for key,value in stats([r[unit] for r in rows]).items():equal(value,expected[unit][key])
    check(actual,summary['main']);check([r for r in actual if r['strict']],summary['strict_hour_quality'])
    for year,x in summary['annual'].items():check([r for r in actual if r['date'].startswith(year)],x)
    for label,x in summary['chronological_halves'].items():check([r for r in actual if (r['date']<'2025-08-29')==(label=='first_year')],x)
    shared=[r for r in actual if r['shared']]
    check(shared,summary['shared_dates_comparison']['one_hour'])
    for unit in ['points','bps']:
        for key,value in stats([r['overnight_'+unit] for r in shared]).items():equal(value,summary['shared_dates_comparison']['full_overnight_'+unit][key])
    for key,value in stats([r['overnight_points']-r['points'] for r in shared]).items():equal(value,summary['shared_dates_comparison']['remaining_overnight_points'][key])
    for cost,x in summary['costs_points'].items():
        for key,value in stats([r['points']-float(cost) for r in actual]).items():equal(value,x['net'][key])
        for a,b in zip(x['net_points_mean_95'],summary['main']['uncertainty']['points_mean_95']):equal(a,b-float(cost))
    baseline_matches=0
    if args.baseline:
        old=json.loads(args.baseline.read_text())['european_hour_bps']
        for key,prior_key in [('hours','n'),('mean','mean'),('median','median'),('positive_pct','win_pct'),('minimum','min'),('maximum','max')]:
            equal(summary['shared_dates_comparison']['one_hour']['bps'][key],old[prior_key]);baseline_matches+=1
    result={'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matches-baseline_matches,
            'original_saved_aggregate_matches':baseline_matches,'made_up_tests_passed':test.testsRun,
            'eligible_hours':len(actual),'source_sha256':summary['source_sha256'],
            'scope':'Separate CSV parsing, UTC/New York conversion, boundary pairing and descriptive aggregates. Mean ranges are not independently implemented; constant cost shifts are checked. Vendor prices are not audited.',
            'python':'3.12.14','numpy':'2.3.5','pandas':'3.0.1','tzdata':'2026.5'}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
