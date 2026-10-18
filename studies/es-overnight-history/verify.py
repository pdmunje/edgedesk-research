"""Independent CSV pairing/counting plus small made-up mechanics tests.

Does not use pandas or the research implementation for the CSV recount.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo
import unittest


def independent_rows(source):
    with source.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    selected = []
    for row, following in zip(rows, rows[1:]):
        start = datetime.fromisoformat(row['time']).astimezone(ZoneInfo('America/New_York'))
        end = datetime.fromisoformat(following['time']).astimezone(ZoneInfo('America/New_York'))
        if (start.hour,start.minute) != (18,0) or (end.hour,end.minute) != (9,30):
            continue
        if end.astimezone(timezone.utc) - start.astimezone(timezone.utc) != timedelta(minutes=930):
            continue
        opening, closing = float(row['open']), float(row['close'])
        selected.append({'date':end.date().isoformat(), 'open':opening,
                         'points':closing-opening, 'bps':(closing/opening-1)*10000,
                         'next_open_bps':(float(following['open'])/opening-1)*10000})
    return selected


def independent_stats(values):
    return {'nights':len(values),'mean':math.fsum(values)/len(values),
            'median':statistics.median(values), 'positive_nights':sum(x>0 for x in values),
            'flat_nights':sum(x==0 for x in values),'negative_nights':sum(x<0 for x in values),
            'positive_pct':sum(x>0 for x in values)/len(values)*100,
            'minimum':min(values),'maximum':max(values)}


class MadeUpChecks(unittest.TestCase):
    def frame(self, times, opens=None, closes=None):
        import pandas as pd
        return pd.DataFrame({'time':times,'open':opens or [100.]*len(times),
                             'close':closes or [101.]*len(times)})

    def test_close_and_next_open_are_different_endpoints(self):
        from reproduce import select_bars
        bars,_ = select_bars(self.frame(['2026-01-04T18:00:00-05:00','2026-01-05T09:30:00-05:00'],[100,102],[101,103]))
        self.assertEqual(bars.points.iloc[0],1)
        self.assertEqual(bars.bps.iloc[0],100)
        self.assertEqual(bars.next_open_points.iloc[0],2)

    def test_partial_bar_is_excluded(self):
        from reproduce import select_bars
        bars,checks = select_bars(self.frame(['2026-01-04T18:00:00-05:00','2026-01-05T01:00:00-05:00','2026-01-05T09:30:00-05:00']))
        self.assertTrue(bars.empty)
        self.assertEqual(len(checks['excluded_candidates']),1)

    def test_following_day_must_be_exactly_930_minutes_later(self):
        from reproduce import select_bars
        bars,_ = select_bars(self.frame(['2026-01-04T18:00:00-05:00','2026-01-06T09:30:00-05:00']))
        self.assertTrue(bars.empty)

    def test_unfinished_final_evening_row_is_excluded(self):
        from reproduce import select_bars
        bars,checks = select_bars(self.frame(['2026-01-04T18:00:00-05:00']))
        self.assertTrue(bars.empty)
        self.assertEqual(checks['excluded_candidates'][0]['reason'],'no following row')

    def test_zero_returns_stay_in_denominator(self):
        result = independent_stats([-1,0,1])
        self.assertEqual(result['positive_nights'],1)
        self.assertAlmostEqual(result['positive_pct'],100/3)

    def test_duplicate_times_are_rejected(self):
        from reproduce import select_bars
        with self.assertRaises(ValueError):
            select_bars(self.frame(['2026-01-04T18:00:00-05:00']*2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--summary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    test_run = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MadeUpChecks))
    if not test_run.wasSuccessful():
        raise AssertionError('Made-up mechanics tests failed.')
    summary = json.loads(args.summary.read_text(encoding='utf-8'))
    observations = independent_rows(args.input)
    matches = 0
    def compare(actual,expected):
        nonlocal matches
        for key,value in actual.items():
            if not math.isclose(value,expected[key],rel_tol=0,abs_tol=1e-9):
                raise AssertionError('Independent recount differs: '+key)
            matches += 1
    groups = [(observations,summary['all_history'])]
    for group in summary['periods'].values():
        groups.append(([r for r in observations if group['first_session']<=r['date']<=group['last_session']],group))
    for year,group in summary['by_year'].items():
        groups.append(([r for r in observations if r['date'].startswith(year)],group))
    for rows,expected in groups:
        for column in ['points','bps']:
            compare(independent_stats([r[column] for r in rows]),expected[column])
    compare(independent_stats([r['next_open_bps'] for r in observations]),summary['close_vs_next_open']['all_history_next_open'])
    for cost,expected in summary['cost_scenarios_all_history'].items():
        compare(independent_stats([r['points']-float(cost) for r in observations]),expected['net_points'])
        compare(independent_stats([(r['points']-float(cost))/r['open']*10000 for r in observations]),expected['net_bps'])
    recent = [r for r in observations if '2024-01-01' <= r['date'] <= '2026-10-05']
    for cost,expected in summary['recent_cost_scenarios'].items():
        compare(independent_stats([r['points']-float(cost) for r in recent]),expected['net_points'])
        compare(independent_stats([(r['points']-float(cost))/r['open']*10000 for r in recent]),expected['net_bps'])
    result = {'passed':True, 'checked_date':'2026-10-15', 'independent_csv_numeric_matches':matches,
              'made_up_mechanics_tests_passed':test_run.testsRun,
              'eligible_nights_recounted':len(observations),
              'source_sha256':summary['source']['sha256'],
              'scope':'Independent parsing, pairing and descriptive statistics; does not independently audit vendor prices, upstream roll rules or bootstrap uncertainty.'}
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
