"""Summarize the supplied continuous-ES evening-to-morning candles.

Inputs are read-only. Only aggregate counts and results are written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

SEED = 20261015
REPLICATES = 5000
PERIODS = [
    ('2000–2010', '2000-01-01', '2010-12-31'),
    ('2011–2020', '2011-01-01', '2020-12-31'),
    ('2021–2023', '2021-01-01', '2023-12-31'),
    ('2024–Oct 5 2026', '2024-01-01', '2026-10-05'),
]


def select_bars(raw):
    raw = raw.copy()
    utc = pd.to_datetime(raw.time, utc=True)
    if not utc.is_monotonic_increasing or utc.duplicated().any():
        raise ValueError('Timestamps must be strictly ordered and unique.')
    if not np.isfinite(raw[['open', 'close']].to_numpy()).all() or (raw.open <= 0).any():
        raise ValueError('Prices must be finite and opening prices positive.')
    local = utc.dt.tz_convert('America/New_York')
    starts = local.dt.strftime('%H:%M').eq('18:00')
    follows = local.shift(-1).dt.strftime('%H:%M').eq('09:30')
    duration = utc.shift(-1).sub(utc).eq(pd.Timedelta(minutes=930))
    valid = starts & follows & duration
    selected = pd.DataFrame({
        'session_date': local.shift(-1).dt.strftime('%Y-%m-%d'),
        'open': raw.open, 'close': raw.close,
        'next_open': raw.open.shift(-1),
    }).loc[valid].copy()
    selected['points'] = selected.close - selected.open
    selected['bps'] = selected.points / selected.open * 10000
    selected['next_open_points'] = selected.next_open - selected.open
    selected['next_open_bps'] = selected.next_open_points / selected.open * 10000
    if selected.session_date.duplicated().any():
        raise ValueError('More than one eligible overnight candle for a date.')
    excluded = []
    for i in np.flatnonzero(starts & ~valid):
        excluded.append({'evening_date': local.iloc[i].strftime('%Y-%m-%d'),
                         'reason': 'no following row' if i == len(raw)-1 else
                           'following row does not start at 09:30' if not follows.iloc[i] else
                           'elapsed time is not 930 minutes'})
    counts = {'raw_rows': len(raw), 'eighteen_start_candidates': int(starts.sum()),
              'other_start_times': int((~starts).sum()),
              'eligible_nights': len(selected), 'excluded_candidates': excluded,
              'first_eligible_session': selected.session_date.min(),
              'last_eligible_session': selected.session_date.max(),
              'time_counts': local.dt.strftime('%H:%M').value_counts().to_dict()}
    return selected, counts


def weekly_interval(frame, column):
    dates = pd.to_datetime(frame.session_date)
    iso = dates.dt.isocalendar()
    weeks = iso.year.astype(str) + '-' + iso.week.astype(str)
    sums = frame.groupby(weeks)[column].agg(['sum', 'count'])
    rng = np.random.default_rng(SEED)
    picks = rng.integers(0, len(sums), size=(REPLICATES, len(sums)))
    values = sums['sum'].to_numpy()[picks].sum(axis=1) / sums['count'].to_numpy()[picks].sum(axis=1)
    return np.quantile(values, [.025, .975]).tolist()


def stats(frame, column):
    values = frame[column].to_numpy()
    return {'nights': len(values), 'mean': float(np.mean(values)),
            'median': float(np.median(values)),
            'positive_nights': int((values > 0).sum()),
            'flat_nights': int((values == 0).sum()),
            'negative_nights': int((values < 0).sum()),
            'positive_pct': float((values > 0).mean()*100),
            'minimum': float(values.min()), 'maximum': float(values.max())}


def group_summary(frame, start=None, end=None):
    if start:
        frame = frame.loc[frame.session_date.between(start, end)].copy()
    return {'first_session': frame.session_date.min(), 'last_session': frame.session_date.max(),
            'points': stats(frame, 'points'), 'bps': stats(frame, 'bps'),
            'mean_bps_weekly_interval_95': weekly_interval(frame, 'bps')}


def overlap_summary(frame, source):
    columns = ['timestamp_utc', 'open', 'underlying_contract', 'session_date']
    with zipfile.ZipFile(source) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Minute ZIP must contain exactly one CSV.')
        minute = pd.read_csv(archive.open(names[0]), usecols=columns, parse_dates=['timestamp_utc'])
    local = minute.timestamp_utc.dt.tz_convert('America/New_York').dt.strftime('%H:%M')
    cuts = minute.loc[local.isin(['18:00','09:30'])].copy()
    cuts['clock'] = local.loc[cuts.index]
    cuts['session_date'] = cuts.session_date.astype(str)
    if cuts.duplicated(['session_date','clock']).any():
        raise ValueError('Duplicate minute boundary.')
    prices = cuts.pivot(index='session_date', columns='clock', values='open')
    contracts = cuts.pivot(index='session_date', columns='clock', values='underlying_contract')
    prices = prices.rename(columns={'18:00':'minute_entry', '09:30':'minute_exit'}).dropna()
    merged = frame.set_index('session_date').join(prices, how='inner').dropna(subset=['minute_entry','minute_exit'])
    merged['minute_points'] = merged.minute_exit - merged.minute_entry
    delta = merged.points - merged.minute_points
    return {'nights': len(merged), 'first_session': str(merged.index.min()),
            'last_session': str(merged.index.max()),
            'mean_candle_points': float(merged.points.mean()),
            'mean_minute_points': float(merged.minute_points.mean()),
            'mean_difference_points': float(delta.mean()),
            'median_absolute_difference_points': float(delta.abs().median()),
            'max_absolute_difference_points': float(delta.abs().max()),
            'difference_above_quarter_point_nights': int((delta.abs() > .25).sum()),
            'difference_above_two_points_nights': int((delta.abs() > 2).sum()),
            'minute_boundary_contract_mismatch_nights': int((contracts.loc[merged.index,'18:00'] != contracts.loc[merged.index,'09:30']).sum()),
            'minute_input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'limitation': 'Boundary comparison only; the all-date overlap is not the stricter quality-filtered minute sample.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Owner-obtained 930-minute continuous ES CSV')
    parser.add_argument('--minute-input', type=Path, required=True, help='Licensed one-minute ES ZIP for source comparison')
    parser.add_argument('--output', type=Path, default=Path('output'))
    args = parser.parse_args()
    frame, checks = select_bars(pd.read_csv(args.input, usecols=['time','open','close']))
    delta = frame.close - frame.next_open
    groups = {name: group_summary(frame, start, end) for name,start,end in PERIODS}
    costs = {}
    for cost in [.5, 1., 2.]:
        net = frame.assign(net_points=frame.points-cost, net_bps=(frame.points-cost)/frame.open*10000)
        costs[str(cost)] = {'net_points': stats(net,'net_points'), 'net_bps': stats(net,'net_bps')}
    recent = frame.loc[frame.session_date.between('2024-01-01','2026-10-05')]
    next_groups = {name: {'bps': stats(frame.loc[frame.session_date.between(start,end)],'next_open_bps')}
                   for name,start,end in PERIODS}
    result = {
        'question': 'How did the supplied ES overnight candle return change across historical periods?',
        'source': {'sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                   'description': 'Owner-obtained continuous ES 930-minute chart CSV; upstream roll and adjustment rules unverified.',
                   'original_prices_not_redistributed': True},
        'checks': checks, 'all_history': group_summary(frame), 'periods': groups,
        'by_year': {str(year): group_summary(g) for year,g in frame.groupby(frame.session_date.str[:4])},
        'close_vs_next_open': {
            'nights': len(frame), 'exact_equal_nights': int(delta.eq(0).sum()),
            'difference_above_one_point_nights': int((delta.abs()>1).sum()),
            'mean_close_minus_next_open_points': float(delta.mean()),
            'mean_close_minus_next_open_bps': float((delta/frame.open*10000).mean()),
            'all_history_next_open': stats(frame,'next_open_bps'),
            'next_open_by_period': next_groups},
        'cost_scenarios_all_history': costs,
        'recent_cost_scenarios': {str(cost): {'net_points': stats(recent.assign(net_points=recent.points-cost),'net_points'),
                                            'net_bps': stats(recent.assign(net_bps=(recent.points-cost)/recent.open*10000),'net_bps')}
                                    for cost in [.5,1.,2.]},
        'overlap_with_minute_source': overlap_summary(frame,args.minute_input),
        'resampling': {'unit':'ISO calendar weeks labelled by morning date', 'replicates': REPLICATES,
                       'random_seed': SEED, 'interval':'2.5th and 97.5th percentiles of resampled means',
                       'method':'Within each displayed group, sample its number of weeks with replacement; retain every night in a sampled week, then divide summed returns by sampled night count.',
                       'limitations':'Chosen period boundaries and changing market conditions are not accounted for by these descriptive intervals.'}}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    rows = [{'period': name, 'first_session': g['first_session'], 'last_session': g['last_session'],
             'nights': g['bps']['nights'], 'mean_bps': g['bps']['mean'], 'median_bps':g['bps']['median'],
             'positive_pct':g['bps']['positive_pct'], 'mean_points':g['points']['mean'],
             'mean_bps_interval_low':g['mean_bps_weekly_interval_95'][0],
             'mean_bps_interval_high':g['mean_bps_weekly_interval_95'][1]} for name,g in groups.items()]
    pd.DataFrame(rows).to_csv(args.output/'period_summary.csv',index=False)
    print(json.dumps({'checks':checks,'periods':groups,'overlap':result['overlap_with_minute_source']},indent=2))


if __name__ == '__main__':
    main()
