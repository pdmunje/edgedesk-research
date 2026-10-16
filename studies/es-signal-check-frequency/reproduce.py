"""Recalculate the effect of checking one ES signal less often.

Original vendor data stays local. Public outputs contain summaries only.
The companion base_analysis.py is the unchanged first-study calculation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd


def periods(states):
    """Lengths of consecutive nonzero states; neutral minutes split periods."""
    found = []
    previous, length = 0, 0
    for value in states:
        value = int(value)
        if value == previous:
            length += 1
        else:
            if previous:
                found.append(length)
            previous, length = value, 1
    if previous:
        found.append(length)
    return found


def hold_to_quarter_hours(states, decision_times):
    """Sample the completed-minute decision at :00/:15/:30/:45, then hold."""
    answer, held = [], 0
    for state, time in zip(states, decision_times):
        if time.minute % 15 == 0:
            held = int(state)
        answer.append(held)
    return np.asarray(answer, dtype=np.int8)


def summarize(frame, column):
    lengths, daily = [], []
    left, right = 0, 0
    for day, group in frame.groupby('session_date', sort=True):
        values = group[column].to_numpy()
        runs = periods(values)
        lengths.extend(runs)
        left += int(values[0] != 0)
        right += int(values[-1] != 0)
        daily.append({'session_date': str(day), 'method': column,
                      'eligible_minutes': len(values),
                      'active_minutes': int(np.count_nonzero(values)),
                      'periods': len(runs),
                      'longest_period_minutes': max(runs, default=0)})
    lengths = np.asarray(lengths)
    long_days = sum(row['longest_period_minutes'] >= 180 for row in daily)
    short = int(np.count_nonzero(lengths <= 30))
    return {
        'sessions': len(daily), 'eligible_minutes': len(frame),
        'active_minutes': int(np.count_nonzero(frame[column])),
        'active_pct': float(np.count_nonzero(frame[column]) / len(frame) * 100),
        'runs': len(lengths), 'runs_per_session': len(lengths) / len(daily),
        'observed_median_minutes': float(np.median(lengths)),
        'observed_mean_minutes': float(np.mean(lengths)),
        'short_periods_at_most_30_minutes': short,
        'observed_at_most_30_pct': short / len(lengths) * 100,
        'minimum_observed_period_minutes': int(lengths.min()),
        'days_with_180_minute_period': long_days,
        'sessions_with_180min_run_pct': long_days / len(daily) * 100,
        'periods_clipped_at_day_start': left,
        'periods_clipped_at_day_end': right,
    }, daily


def compare_with_base(calculated, reference):
    keys = ['sessions', 'eligible_minutes', 'active_pct', 'runs',
            'runs_per_session', 'observed_median_minutes',
            'observed_mean_minutes', 'observed_at_most_30_pct',
            'sessions_with_180min_run_pct']
    for key in keys:
        if not np.isclose(calculated[key], reference[key], rtol=0, atol=1e-10):
            raise AssertionError(f'Independent count differs: {key}')
    return len(keys)


def analyze(base_directory):
    base = json.loads((base_directory / 'results.json').read_text())
    frame = pd.read_csv(base_directory / 'minute_signals.csv.gz',
                        usecols=['timestamp_utc', 'session_date', 'B', 'rth_eligible'],
                        parse_dates=['timestamp_utc'])
    frame['decision_time'] = frame.timestamp_utc + pd.Timedelta(minutes=1)
    frame['held_15m'] = hold_to_quarter_hours(frame.B, frame.decision_time)
    selected = frame.loc[frame.rth_eligible].copy()
    assert selected.groupby('session_date').size().eq(390).all()
    for _, group in selected.groupby('session_date'):
        assert group.decision_time.diff().dropna().dt.total_seconds().eq(60).all()
        times = group.decision_time.dt.tz_convert('America/New_York')
        assert (times.iloc[0].hour, times.iloc[0].minute) == (9, 30)
        assert (times.iloc[-1].hour, times.iloc[-1].minute) == (15, 59)
    raw, daily_raw = summarize(selected, 'B')
    held, daily_held = summarize(selected, 'held_15m')
    comparisons = compare_with_base(raw, base['primary']['B'])
    comparisons += compare_with_base(held, base['B_quarter_hour_decisions'])
    assert held['minimum_observed_period_minutes'] >= 15
    # Every decision change within a day must be at a quarter-hour boundary.
    previous = selected.held_15m.shift()
    same_day = selected.session_date.eq(selected.session_date.shift())
    changed = selected.held_15m.ne(previous) & same_day
    assert selected.loc[changed, 'decision_time'].dt.minute.mod(15).eq(0).all()
    raw_values, held_values = selected.B, selected.held_15m
    disagreement = {
        'eligible_minutes': len(selected),
        'different_decision_minutes': int(raw_values.ne(held_values).sum()),
        'held_active_but_minute_neutral_minutes': int((held_values.ne(0) & raw_values.eq(0)).sum()),
        'held_neutral_but_minute_active_minutes': int((held_values.eq(0) & raw_values.ne(0)).sum()),
        'opposite_active_directions_minutes': int((held_values * raw_values == -1).sum()),
    }
    disagreement['different_decision_pct'] = disagreement['different_decision_minutes'] / len(selected) * 100
    assert disagreement['different_decision_minutes'] == sum(disagreement[k] for k in [
        'held_active_but_minute_neutral_minutes',
        'held_neutral_but_minute_active_minutes', 'opposite_active_directions_minutes'])
    midpoint = base['checks']['half_split_session']
    halves = {}
    for name, mask in [('earlier_half', selected.session_date.lt(midpoint)),
                       ('later_half', selected.session_date.ge(midpoint))]:
        subset = selected.loc[mask]
        halves[name] = {'first_session': str(subset.session_date.min()),
                        'last_session': str(subset.session_date.max()),
                        'every_minute': summarize(subset, 'B')[0],
                        'every_15_minutes': summarize(subset, 'held_15m')[0]}
    result = {'question': 'What changes when the same minute signal is checked every 15 minutes?',
              'source': base['checks'],
              'measurement': {'timezone': 'America/New_York', 'start_inclusive': '09:30',
                              'end_exclusive': '16:00',
                              'first_eligible_session': str(selected.session_date.min()),
                              'last_eligible_session': str(selected.session_date.max()),
                              'half_split_session': midpoint},
              'every_minute': raw, 'every_15_minutes': held,
              'different_decisions': disagreement, 'sample_halves': halves,
              'verification': {'independent_summary_values_matched': comparisons,
                               'complete_390_minute_days_checked': raw['sessions'],
                               'quarter_hour_changes_only': True,
                               'disagreement_categories_reconcile': True,
                               'base_analysis_sha256': hashlib.sha256(
                                   Path(__file__).with_name('base_analysis.py').read_bytes()).hexdigest()}}
    return result, daily_raw + daily_held


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True,
                        help='Licensed ES minute CSV or one-CSV ZIP; read-only')
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Intermediate files contain prices and are never part of the public output.
    with tempfile.TemporaryDirectory(prefix='.private-intermediate-', dir=args.output.resolve()) as temporary:
        base_directory = Path(temporary)
        assert base_directory.resolve().is_relative_to(args.output.resolve())
        completed = subprocess.run([sys.executable,
            str(Path(__file__).with_name('base_analysis.py')),
            '--input', str(args.input.resolve()), '--output', str(base_directory)],
            capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError('Base calculation failed:\n' + completed.stderr)
        result, daily = analyze(base_directory)
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    pd.DataFrame(daily).to_csv(args.output / 'daily_counts.csv', index=False)
    print(json.dumps({'sessions': result['every_minute']['sessions'],
                      'every_minute': result['every_minute'],
                      'every_15_minutes': result['every_15_minutes'],
                      'different_decisions': result['different_decisions'],
                      'verification': result['verification']}, indent=2))


if __name__ == '__main__':
    main()
