"""Independent CSV/date recount plus clearly made-up mechanics tests."""
import argparse
import csv
from datetime import datetime, timedelta
import io
import json
import math
from pathlib import Path
import statistics
import tempfile
import unittest
import zipfile
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
FIXTURES = None


def recount(source):
    by_instant = {};by_local = {};sessions = {};days = {}
    with zipfile.ZipFile(source) as archive:
        names = [x for x in archive.namelist() if x.lower().endswith('.csv')]
        assert len(names)==1
        previous = None
        with archive.open(names[0]) as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle,encoding='utf-8-sig')):
                t = datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
                assert previous is None or t>previous
                previous = t
                assert row['is_complete'].lower()=='true'
                local = t.astimezone(NY);clock = (local.hour,local.minute)
                bad = row['data_condition']=='degraded' or row['roll_transition'].lower()=='true'
                s = sessions.setdefault(row['session_date'],{'count':0,'bad':False})
                s['bad'] |= bad
                if clock>=(18,0) or clock<(9,30):s['count']+=1
                d = days.setdefault(local.date(),{'count':0,'bad':False})
                if (9,30)<=clock<(16,0):d['count']+=1
                if (9,30)<=clock<=(16,0):d['bad'] |= bad
                if clock in [(9,30),(16,0),(18,0)]:
                    r = {'time':t,'local':local,'price':float(row['open']),
                         'contract':row['underlying_contract'],'session':row['session_date']}
                    assert math.isfinite(r['price']) and r['price']>0
                    assert (local.date(),clock) not in by_local
                    by_local[local.date(),clock]=r;by_instant[t]=r
    found = []
    for entry in by_instant.values():
        local = entry['local']
        if (local.hour,local.minute)!=(18,0):continue
        end = by_instant.get(entry['time']+timedelta(minutes=930))
        if end is None or (end['local'].hour,end['local'].minute)!=(9,30):continue
        if entry['contract']!=end['contract'] or entry['session']!=end['session']:continue
        assert end['local'].date().isoformat()==entry['session']
        assert local.weekday() in [0,1,2,3,6]
        sunday = local.weekday()==6
        prior = local.date()-timedelta(days=2 if sunday else 0)
        a = by_local.get((prior,(9,30)));b = by_local.get((prior,(16,0)))
        if a is None or b is None:continue
        if len({a['contract'],b['contract'],entry['contract'],end['contract']})!=1:continue
        if b['time']-a['time']!=timedelta(minutes=390):continue
        assert b['time']<entry['time']
        strict = sessions[entry['session']]['count']==930 and not sessions[entry['session']]['bad'] and days[prior]['count']==390 and not days[prior]['bad']
        points = end['price']-entry['price']
        found.append({'date':entry['session'],'negative':b['price']<a['price'],
                      'sunday':sunday,'strict':strict,'points':points,'bps':points/entry['price']*10000})
    return sorted(found,key=lambda x:x['date'])


def stats(x):
    return {'nights':len(x),'mean':math.fsum(x)/len(x),'median':statistics.median(x),
            'positive_nights':sum(v>0 for v in x),'flat_nights':sum(v==0 for v in x),
            'positive_pct':100*sum(v>0 for v in x)/len(x),'minimum':min(x),'maximum':max(x)}


class MadeUpChecks(unittest.TestCase):
    def source(self,rows):
        target = Path(FIXTURES)/'fixture.zip'
        header = 'timestamp_utc,session_date,open,underlying_contract,data_condition,is_complete,roll_transition\n'
        with zipfile.ZipFile(target,'w') as z:z.writestr('bars.csv',header+'\n'.join(sorted(rows)))
        return target

    def normal(self,day_close=4990):
        return ['2026-01-05T14:30:00Z,2026-01-05,5000,ESH6,available,true,false',
                f'2026-01-05T21:00:00Z,2026-01-05,{day_close},ESH6,available,true,false',
                '2026-01-05T23:00:00Z,2026-01-06,5000,ESH6,available,true,false',
                '2026-01-06T14:30:00Z,2026-01-06,5005,ESH6,available,true,false']

    def both(self,rows):
        from reproduce import observations
        source = self.source(rows)
        a,_ = observations(source);b = recount(source)
        self.assertEqual(len(a),len(b))
        return a,b

    def test_negative_day_and_known_before_entry(self):
        a,b = self.both(self.normal())
        self.assertTrue(a.negative.iloc[0]);self.assertTrue(b[0]['negative'])
        self.assertEqual(a.points.iloc[0],5)

    def test_flat_day_is_in_nonnegative_group(self):
        a,b = self.both(self.normal(5000))
        self.assertFalse(a.negative.iloc[0]);self.assertFalse(b[0]['negative'])

    def test_sunday_uses_exact_friday(self):
        rows = ['2026-01-02T14:30:00Z,2026-01-02,5000,ESH6,available,true,false',
                '2026-01-02T21:00:00Z,2026-01-02,4990,ESH6,available,true,false',
                '2026-01-04T23:00:00Z,2026-01-05,5000,ESH6,available,true,false',
                '2026-01-05T14:30:00Z,2026-01-05,5005,ESH6,available,true,false']
        a,b = self.both(rows)
        self.assertTrue(a.sunday.iloc[0]);self.assertTrue(b[0]['sunday'])

    def test_sunday_does_not_substitute_thursday_for_missing_friday(self):
        rows = ['2026-01-01T14:30:00Z,2026-01-01,5000,ESH6,available,true,false',
                '2026-01-01T21:00:00Z,2026-01-01,4990,ESH6,available,true,false',
                '2026-01-04T23:00:00Z,2026-01-05,5000,ESH6,available,true,false',
                '2026-01-05T14:30:00Z,2026-01-05,5005,ESH6,available,true,false']
        a,_ = self.both(rows);self.assertTrue(a.empty)

    def test_missing_daytime_boundary_excluded(self):
        a,_ = self.both([x for x in self.normal() if '21:00' not in x]);self.assertTrue(a.empty)

    def test_changed_contract_between_day_and_night_excluded(self):
        rows = [x.replace('ESH6','ESM6') if '2026-01-06,' in x else x for x in self.normal()]
        a,_ = self.both(rows);self.assertTrue(a.empty)

    def test_missing_morning_exit_excluded(self):
        a,_ = self.both(self.normal()[:-1]);self.assertTrue(a.empty)

    def test_flat_night_remains_in_percentage_denominator(self):
        self.assertAlmostEqual(stats([-1,0,1])['positive_pct'],100/3)

    def test_constant_paired_groups_keep_bootstrap_difference(self):
        import pandas as pd
        from reproduce import interval
        frame = pd.DataFrame({'negative':[True,False]*3,'bps':[3,1]*3,
                              'date':['2026-01-05','2026-01-06','2026-01-12','2026-01-13','2026-01-19','2026-01-20']})
        self.assertEqual(interval(frame)['difference_down_minus_other_bps_95'],[2,2])


def main():
    global FIXTURES
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--summary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='.made-up-',dir=args.output.parent.resolve()) as folder:
        FIXTURES = folder
        tests = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
        if not tests.wasSuccessful():raise AssertionError('Mechanics checks failed.')
    rows = recount(args.input)
    result = json.loads(args.summary.read_text())
    matches = 0
    def equal(a,b):
        nonlocal matches
        assert math.isclose(a,b,rel_tol=0,abs_tol=1e-9),(a,b)
        matches+=1
    def check(selected,expected):
        for side,negative in [('down',True),('other',False)]:
            chosen = [r for r in selected if r['negative']==negative]
            for unit in ['points','bps']:
                for key,value in stats([r[unit] for r in chosen]).items():equal(value,expected[side][unit][key])
        equal(expected['uncertainty']['difference_bps'],
              stats([r['bps'] for r in selected if r['negative']])['mean']-
              stats([r['bps'] for r in selected if not r['negative']])['mean'])
    check(rows,result['main'])
    check([r for r in rows if not r['sunday']],result['other_weekday_entries'])
    check([r for r in rows if r['sunday']],result['sunday_entries'])
    check([r for r in rows if r['strict']],result['stricter'])
    for year,expected in result['annual'].items():check([r for r in rows if r['date'].startswith(year)],expected)
    for label,expected in result['chronological_halves'].items():
        check([r for r in rows if (r['date']<'2025-08-29')==(label=='first_year')],expected)
    for cost,expected in result['costs_points'].items():
        for side,negative in [('down',True),('other',False)]:
            for key,value in stats([r['points']-float(cost) for r in rows if r['negative']==negative]).items():equal(value,expected[side][key])
    for unit in ['points','bps']:
        for key,value in stats([r[unit] for r in rows]).items():equal(value,result['unfiltered_eligible'][unit][key])
    equal(len(rows),result['checks']['eligible_with_required_daytime'])
    verified = {'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matches,
                'made_up_tests_passed':tests.testsRun,'eligible_nights':len(rows),
                'source_sha256':result['source_sha256'],
                'scope':'Separate standard-library CSV parser, timestamp pairing, daytime mapping and descriptive aggregates. Bootstrap ranges and vendor prices are not independently audited.',
                'python':'3.12.14','numpy':'2.3.5','pandas':'3.0.1','tzdata':'2026.5'}
    args.output.write_text(json.dumps(verified,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(verified,indent=2))


if __name__=='__main__':main()
