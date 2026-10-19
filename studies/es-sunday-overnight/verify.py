"""Independently parse source rows, pair actual nights and recount summaries."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
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
TEST_FOLDER=None


def minute_rows(source):
    sessions={}
    previous=None
    with zipfile.ZipFile(source) as archive:
        names=[x for x in archive.namelist() if x.lower().endswith('.csv')]
        assert len(names)==1
        with archive.open(names[0]) as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle,encoding='utf-8-sig')):
                instant=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
                assert previous is None or instant>previous
                previous=instant
                assert row['is_complete'].lower()=='true'
                local=instant.astimezone(NY)
                day=sessions.setdefault(row['session_date'],{'cuts':{},'count':0,'degraded':False,'roll':False})
                clock=(local.hour,local.minute)
                day['degraded'] |= row['data_condition']=='degraded'
                day['roll'] |= row['roll_transition'].lower()=='true'
                if clock>=(18,0) or clock<(9,30): day['count']+=1
                if clock in [(18,0),(9,30)]:
                    assert clock not in day['cuts']
                    day['cuts'][clock]=(instant,local,float(row['open']),row['underlying_contract'])
    found=[]
    for source_date,rec in sorted(sessions.items()):
        if set(rec['cuts'])!={(18,0),(9,30)}:continue
        start,local_start,opening,contract_in=rec['cuts'][(18,0)]
        end,local_end,closing,contract_out=rec['cuts'][(9,30)]
        if contract_in!=contract_out or end-start!=timedelta(minutes=930):continue
        assert local_end.date().isoformat()==source_date
        if local_start.weekday()==6:assert local_end.weekday()==0
        else:assert local_start.weekday() in [0,1,2,3]
        found.append({'date':source_date,'entry_weekday':local_start.strftime('%A'),
                      'sunday':local_start.weekday()==6,'entry':opening,
                      'strict':not rec['degraded'] and not rec['roll'] and rec['count']==930,
                      'points':closing-opening,'bps':(closing/opening-1)*10000})
    return found


def historical_rows(source):
    with source.open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
    found=[]
    for row,next_row in zip(rows,rows[1:]):
        start=datetime.fromisoformat(row['time']).astimezone(NY)
        end=datetime.fromisoformat(next_row['time']).astimezone(NY)
        if (start.hour,start.minute)!=(18,0) or (end.hour,end.minute)!=(9,30):continue
        if end.astimezone(timezone.utc)-start.astimezone(timezone.utc)!=timedelta(minutes=930):continue
        opening,closing=float(row['open']),float(row['close'])
        found.append({'date':end.date().isoformat(),'sunday':start.weekday()==6,
                      'points':closing-opening,'bps':(closing/opening-1)*10000})
    return found


def stats(values):
    return {'nights':len(values),'mean':math.fsum(values)/len(values),'median':statistics.median(values),
            'positive_nights':sum(x>0 for x in values),'flat_nights':sum(x==0 for x in values),
            'positive_pct':sum(x>0 for x in values)/len(values)*100,
            'minimum':min(values),'maximum':max(values)}


class MadeUpChecks(unittest.TestCase):
    def fixture(self,rows):
        filename=Path(TEST_FOLDER)/'fixture.zip'
        header='timestamp_utc,session_date,open,underlying_contract,data_condition,is_complete,roll_transition\n'
        with zipfile.ZipFile(filename,'w') as archive:archive.writestr('input.csv',header+'\n'.join(rows))
        return filename

    def test_actual_sunday_entry_is_monday_exit(self):
        from reproduce import minute_nights
        source=self.fixture(['2026-01-04T23:00:00Z,2026-01-05,5000,ESH6,available,true,false',
                             '2026-01-05T14:30:00Z,2026-01-05,5005,ESH6,available,true,false'])
        a,_=minute_nights(source)
        b=minute_rows(source)
        self.assertTrue(a.sunday.iloc[0]);self.assertTrue(b[0]['sunday'])
        self.assertEqual(a.points.iloc[0],5)

    def test_different_contracts_are_excluded(self):
        from reproduce import minute_nights
        source=self.fixture(['2026-01-04T23:00:00Z,2026-01-05,5000,ESH6,available,true,false',
                             '2026-01-05T14:30:00Z,2026-01-05,5005,ESM6,available,true,false'])
        a,c=minute_nights(source)
        self.assertTrue(a.empty);self.assertEqual(len(c['contract_mismatch_dates']),1)

    def test_wrong_elapsed_time_is_excluded(self):
        from reproduce import minute_nights
        source=self.fixture(['2026-01-04T23:00:00Z,2026-01-06,5000,ESH6,available,true,false',
                             '2026-01-06T14:30:00Z,2026-01-06,5005,ESH6,available,true,false'])
        a,c=minute_nights(source)
        self.assertTrue(a.empty);self.assertEqual(len(c['wrong_elapsed_time_dates']),1)

    def test_missing_exit_does_not_get_filled(self):
        from reproduce import minute_nights
        source=self.fixture(['2026-01-04T23:00:00Z,2026-01-05,5000,ESH6,available,true,false'])
        a,c=minute_nights(source)
        self.assertTrue(a.empty);self.assertEqual(len(c['missing_exit_dates']),1)

    def test_flat_nights_stay_in_the_denominator(self):
        self.assertAlmostEqual(stats([-1,0,1])['positive_pct'],100/3)

    def test_pooled_nights_use_each_observation_not_equal_weekday_means(self):
        self.assertEqual(stats([1,3,3,3])['mean'],2.5)

    def test_constant_groups_preserve_bootstrap_difference(self):
        import pandas as pd
        from reproduce import interval
        frame=pd.DataFrame({'sunday':[True,False]*3,'bps':[3,1]*3},
                           index=['2026-01-05','2026-01-06','2026-01-12','2026-01-13','2026-01-19','2026-01-20'])
        result=interval(frame)
        self.assertEqual(result['difference_sunday_minus_other_bps_95'],[2,2])


def main():
    global TEST_FOLDER
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--history-input',required=True,type=Path)
    parser.add_argument('--summary',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--baseline',type=Path,help='Optional freshly rerun original minute-study summary')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='.private-fixtures-',dir=args.output.parent.resolve()) as folder:
        assert Path(folder).resolve().is_relative_to(args.output.parent.resolve())
        TEST_FOLDER=folder
        tests=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
        if not tests.wasSuccessful():raise AssertionError('Made-up checks failed.')
    source=json.loads(args.summary.read_text())
    minute=minute_rows(args.input);history=historical_rows(args.history_input)
    matched=0
    def equal(a,b):
        nonlocal matched
        assert math.isclose(a,b,rel_tol=0,abs_tol=1e-9),(a,b)
        matched+=1
    def check(rows,expected):
        for side,sunday in [('sunday',True),('other',False)]:
            selected=[r for r in rows if r['sunday']==sunday]
            for unit in ['points','bps']:
                for key,value in stats([r[unit] for r in selected]).items():equal(value,expected[side][unit][key])
    check(minute,source['main'])
    check([r for r in minute if r['strict']],source['stricter'])
    for year,expected in source['minute_by_year'].items():check([r for r in minute if r['date'].startswith(year)],expected)
    bounds=[('2000-01-01','2010-12-31'),('2011-01-01','2020-12-31'),('2021-01-01','2023-12-31'),('2024-01-01','2026-10-05')]
    for expected,(start,end) in zip(source['historical_periods'].values(),bounds):check([r for r in history if start<=r['date']<=end],expected)
    check([r for r in history if r['date'] in {x['date'] for x in minute}],source['historical_overlap_same_515_dates'])
    for day,expected in source['all_entry_weekdays'].items():
        for unit in ['points','bps']:
            for key,value in stats([r[unit] for r in minute if r['entry_weekday']==day]).items():equal(value,expected[unit][key])
    for cost,expected in source['costs_points_per_night'].items():
        for side,sunday in [('sunday',True),('other',False)]:
            rows=[r for r in minute if r['sunday']==sunday]
            for key,value in stats([r['points']-float(cost) for r in rows]).items():equal(value,expected[side]['net_points'][key])
            for key,value in stats([(r['points']-float(cost))/r['entry']*10000 for r in rows]).items():equal(value,expected[side]['net_bps'][key])
    selected=sorted([r for r in minute if r['sunday']],key=lambda r:abs(r['bps']))[:-5]
    for unit in ['points','bps']:
        for key,value in stats([r[unit] for r in selected]).items():equal(value,source['remove_five_largest_absolute_sunday_moves'][unit][key])
    baseline_matches=0
    if args.baseline:
        old=json.loads(args.baseline.read_text())
        mapping={'nights':'n','mean':'mean','median':'median','positive_pct':'win_pct','minimum':'min','maximum':'max'}
        for unit in ['points','bps']:
            sunday=old['weekday_points' if unit=='points' else 'weekday']['Monday']
            other=old['nonmonday'][unit]
            for side,prior in [('sunday',sunday),('other',other)]:
                for a,b in mapping.items():
                    assert math.isclose(source['main'][side][unit][a],prior[b],rel_tol=0,abs_tol=1e-9)
                    baseline_matches+=1
    result={'passed':True,'checked_date':'2026-10-15','independent_numeric_matches':matched,
            'original_minute_rerun_values_matched':baseline_matches,'made_up_tests_passed':tests.testsRun,
            'minute_nights':len(minute),'historical_nights':len(history),
            'source_sha256':source['source_sha256'],
            'scope':'Independent CSV parsing, time pairing and descriptive counts. Vendor prices and bootstrap ranges are not independently audited.',
            'python':'3.12.14','numpy':'2.3.5','pandas':'3.0.1','tzdata':'2026.5'}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
