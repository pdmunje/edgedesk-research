"""Reproduce a fixed 18:00-to-09:30 ES return study without redistributing bars."""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile
from zoneinfo import ZoneInfo

import base_analysis

NY = ZoneInfo('America/New_York')


def truth(value):
    return str(value).lower() == 'true'


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def independently_count(path, result):
    """A second parser uses csv and Python arithmetic rather than pandas pivots."""
    sessions, rows = {}, 0
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1 or not names[0].lower().endswith('.csv'):
            raise ValueError('Expected exactly one CSV member in the archive.')
        with archive.open(names[0]) as stream:
            for row in csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig')):
                rows += 1
                if not truth(row['is_complete']):
                    raise ValueError('Incomplete bars need an explicit new study policy.')
                clock = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00')).astimezone(NY)
                day = row['session_date']
                record = sessions.setdefault(day, {'cuts': {}, 'bars': 0, 'degraded': False, 'roll': False})
                record['degraded'] |= row['data_condition'] == 'degraded'
                record['roll'] |= truth(row['roll_transition'])
                minute = clock.hour * 60 + clock.minute
                if minute >= 1080 or minute < 570:
                    record['bars'] += 1
                if clock.strftime('%H:%M') in ('18:00', '09:30'):
                    key = clock.strftime('%H:%M')
                    if key in record['cuts']:
                        raise ValueError('Duplicate boundary bar.')
                    record['cuts'][key] = (float(row['open']), row['underlying_contract'])
    eligible, clean, years = [], [], {}
    for day, rec in sorted(sessions.items()):
        if set(rec['cuts']) != {'18:00', '09:30'}:
            continue
        entry, contract_in = rec['cuts']['18:00']
        exit_price, contract_out = rec['cuts']['09:30']
        if contract_in != contract_out:
            continue
        points = exit_price - entry
        bp = (exit_price / entry - 1) * 10000
        eligible.append((points, bp))
        years.setdefault(day[:4], []).append(bp)
        if not rec['degraded'] and not rec['roll'] and rec['bars'] == 930:
            clean.append((points, bp))
    assertions = 0

    def equal(actual, expected):
        nonlocal assertions
        if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-9):
            raise AssertionError((actual, expected))
        assertions += 1

    equal(rows, result['checks']['rows'])
    equal(sum(bool(rec['cuts']) for rec in sessions.values()), result['checks']['session_dates'])
    equal(len(eligible), result['overall']['points']['n'])
    for column, key in [(0, 'points'), (1, 'bps')]:
        values = [x[column] for x in eligible]
        equal(math.fsum(values), result['overall'][key]['sum'])
        equal(math.fsum(values) / len(values), result['overall'][key]['mean'])
        equal(sum(x > 0 for x in values) * 100 / len(values), result['overall'][key]['win_pct'])
        equal(min(values), result['overall'][key]['min'])
        equal(max(values), result['overall'][key]['max'])
    equal(len(clean), result['quality']['clean_only']['n'])
    equal(math.fsum(x[1] for x in clean) / len(clean), result['quality']['clean_only']['mean'])
    for cost in (0.5, 1.0, 2.0):
        values = [x[0] - cost for x in eligible]
        saved = result['cost_scenarios_points'][str(cost)]
        equal(math.fsum(values) / len(values), saved['mean'])
        equal(sum(x > 0 for x in values) * 100 / len(values), saved['win_pct'])
    for year, values in years.items():
        equal(len(values), result['calendar_year'][year]['n'])
        equal(math.fsum(values) / len(values), result['calendar_year'][year]['mean'])
    # Constant trading costs shift every bootstrap sample mean by the same amount.
    gross_ci = result['bootstrap_ci95']['overall_points']
    assert gross_ci[0] < result['overall']['points']['mean'] < gross_ci[1]
    return {'independent_numeric_checks': assertions, 'source_session_dates': len(sessions), 'eligible_sessions': len(eligible),
            'stricter_sessions': len(clean), 'positive_gross_sessions': sum(p > 0 for p, _ in eligible),
            'method': 'Separate csv parser, boundary pairing and Python arithmetic; no raw bars exported.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    source_hash = fingerprint(args.input)
    base_analysis.ZIP_PATH = args.input
    result = base_analysis.main()
    complete_states = {str(value).lower() for value in result['checks']['complete_counts']}
    if result['checks']['duplicate_timestamps'] or complete_states != {'true'}:
        raise ValueError('Duplicates or incomplete bars require a newly documented policy.')
    verification = independently_count(args.input, result)
    if source_hash != fingerprint(args.input):
        raise AssertionError('The input changed during the calculation.')
    result['source_sha256'] = source_hash
    result['cost_intervals_points'] = {str(c): [v - c for v in result['bootstrap_ci95']['overall_points']] for c in (0.5, 1.0, 2.0)}
    verification.update({'passed': True, 'source_sha256': source_hash, 'source_unchanged': True,
                         'bootstrap_repetitions': 20000, 'bootstrap_unit': 'calendar week',
                         'bootstrap_seed': 20261010, 'human_publication_approval': None})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'summary.json').write_text(json.dumps(result, indent=2, default=str) + '\n', encoding='utf-8')
    (args.output_dir / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verification, indent=2))


if __name__ == '__main__':
    main()
