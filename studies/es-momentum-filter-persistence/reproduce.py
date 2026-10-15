"""Compare ES completed-bar and minute-updated trend/momentum persistence.

Read-only input; local outputs go to --output. No trade execution.
Public research support only: original vendor prices are not distributed.
"""
from pathlib import Path
import hashlib
import html
import json
import zipfile

import numpy as np
import pandas as pd
import argparse

OUT = Path(__file__).resolve().parent
SOURCE = None
TZ = "America/New_York"
NAMES = {
    "A": "A: 15m momentum + hourly EMA20",
    "B": "B: 1m momentum(60) + minute EMA1200",
    "C": "Control: 15m momentum + minute EMA1200",
    "D": "Control: 1m momentum(60) + hourly EMA20",
    "A_confirm": "A with two hourly trend confirmations",
    "B_confirm": "B with two hourly trend confirmations",
    "trend_A": "Hourly EMA20 trend alone",
    "trend_B": "Minute EMA1200 trend alone",
}


def aligned(trend, momentum):
    return np.where((trend == momentum) & (trend != 0), trend, 0).astype(np.int8)


def aggregate(d, freq, count):
    t = d.assign(bucket=d.timestamp_utc.dt.floor(freq))
    a = t.groupby(["segment", "bucket"], sort=True).agg(
        close=("close", "last"), count=("close", "size"))
    a = a[a["count"] == count].reset_index()
    a["end"] = a.bucket + pd.Timedelta(minutes=count)
    return a.set_index("end").sort_index()


def confirmed_hourly(values):
    """Two consecutive hourly nonzero candidate readings; zero breaks streak."""
    result = np.zeros(len(values), dtype=np.int8)
    state, prior = 0, 0
    for i, x in enumerate(values):
        x = int(x) if np.isfinite(x) else 0
        if x != 0 and x == prior:
            state = x
        result[i] = state
        prior = x
    return result


def runs_for(signal, frame, selected, label, window):
    pos = np.flatnonzero(selected)
    if not len(pos):
        return pd.DataFrame()
    # Numeric timestamp units are intentionally avoided for interval arithmetic.
    contiguous = frame.timestamp_utc.diff().dt.total_seconds().eq(60).to_numpy()
    sessions = frame.session_date.to_numpy()
    breaks = np.r_[True, (np.diff(pos) != 1) | ~contiguous[pos[1:]] |
                   (sessions[pos[1:]] != sessions[pos[:-1]])]
    blocks = np.cumsum(breaks)
    s = signal[pos]
    edges = np.r_[0, np.flatnonzero((s[1:] != s[:-1]) | breaks[1:]) + 1, len(pos)]
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        side = int(s[a])
        if side == 0:
            continue
        left = bool(a == 0 or breaks[a])
        right = bool(b == len(pos) or breaks[b])
        p, q = int(pos[a]), int(pos[b - 1])
        # A signal calculated at the minute close applies to the next interval.
        start = frame.end.iloc[p]
        finish = frame.end.iloc[q] + pd.Timedelta(minutes=1)
        rows.append({"model": label, "window": window,
                     "session_date": sessions[p], "direction": side,
                     "start_utc": str(start), "end_utc": str(finish),
                     "duration_minutes": b - a, "left_censored": left,
                     "right_censored": right, "start_position": p,
                     "end_position": q, "block": int(blocks[a])})
    return pd.DataFrame(rows)


def km_summary(runs):
    """Natural starts only; window/gap-end runs are right-censored."""
    a = runs[~runs.left_censored]
    if a.empty:
        return {}
    grouped = a.groupby("duration_minutes").agg(n=("direction", "size"),
                                                censored=("right_censored", "sum"))
    at_risk, surv, median = len(a), 1.0, None
    answers = {}
    for duration, g in grouped.iterrows():
        for horizon in [15, 30, 60, 180, 240]:
            if duration >= horizon and str(horizon) not in answers:
                answers[str(horizon)] = surv * 100
        events = int(g.n - g.censored)
        surv *= 1 - events / at_risk
        if median is None and surv <= .5:
            median = int(duration)
        at_risk -= int(g.n)
    # No extrapolation when the longest observed run is shorter than a horizon.
    for horizon in [15, 30, 60, 180, 240]:
        answers.setdefault(str(horizon), 0.0 if surv == 0 else None)
    return {"natural_starts": len(a), "right_censored": int(a.right_censored.sum()),
            "median_minutes": median, "survive_at_least_minutes_pct": answers}


def describe(signal, frame, selected, label, window):
    r = runs_for(signal, frame, selected, label, window)
    days = frame.loc[selected, "session_date"].unique()
    duration = r.duration_minutes
    active = signal[selected] != 0
    counts = r.groupby("session_date").size().reindex(days, fill_value=0)
    maxima = r.groupby("session_date").duration_minutes.max().reindex(days, fill_value=0)
    entry = r[~r.left_censored]
    completed = entry[~entry.right_censored]
    # Fixed horizon diagnostic only; no position or path crosses window edges.
    forward = {}
    for horizon in [30, 60, 180]:
        points = []
        for row in entry.itertuples():
            p, q = row.start_position + 1, row.start_position + 1 + horizon
            if q >= len(frame) or not selected[p:q+1].all():
                continue
            if frame.session_date.iloc[q] != frame.session_date.iloc[p]:
                continue
            if (frame.timestamp_utc.iloc[q] - frame.timestamp_utc.iloc[p]).total_seconds() != horizon * 60:
                continue
            points.append(row.direction * (frame.open.iloc[q] - frame.open.iloc[p]))
        forward[str(horizon)] = {"n": len(points),
                                  "mean_signed_points": float(np.mean(points)) if points else None,
                                  "positive_pct": float(np.mean(np.asarray(points) > 0)*100) if points else None}
    bins = [(1, 5), (6, 15), (16, 30), (31, 60), (61, 120), (121, 180), (181, 240), (241, 10000)]
    summary = {
        "sessions": len(days), "eligible_minutes": int(selected.sum()),
        "active_pct": float(active.mean()*100), "runs": len(r),
        "runs_per_session": float(counts.mean()),
        "natural_entries_per_session": float(len(entry)/len(days)),
        "observed_median_minutes": float(duration.median()),
        "observed_mean_minutes": float(duration.mean()),
        "observed_p90_minutes": float(duration.quantile(.9)),
        "observed_under_15_pct": float(duration.lt(15).mean()*100),
        "observed_at_most_30_pct": float(duration.le(30).mean()*100),
        "observed_at_least_180_pct": float(duration.ge(180).mean()*100),
        "observed_at_least_240_pct": float(duration.ge(240).mean()*100),
        "active_time_in_runs_at_least_180_pct": float(duration[duration.ge(180)].sum()/duration.sum()*100),
        "sessions_with_180min_run_pct": float(maxima.ge(180).mean()*100),
        "median_longest_run_per_session_minutes": float(maxima.median()),
        "left_censored_runs": int(r.left_censored.sum()),
        "right_censored_runs": int(r.right_censored.sum()),
        "completed_natural_runs": len(completed),
        "completed_natural_median_minutes": float(completed.duration_minutes.median()),
        "km": km_summary(r), "entry_forward_diagnostics": forward,
        "duration_bins": {f"{lo}-{hi}": int(duration.between(lo, hi).sum()) for lo, hi in bins},
    }
    return summary, r


def main():
    global SOURCE, OUT
    parser = argparse.ArgumentParser(description="Reproduce the ES momentum/trend persistence comparison.")
    parser.add_argument('--input', type=Path, required=True, help='Licensed minute CSV or ZIP containing it')
    parser.add_argument('--output', type=Path, default=Path('output'), help='Local output directory (not for public upload)')
    args = parser.parse_args()
    SOURCE = args.input.resolve()
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["timestamp_utc", "open", "close", "underlying_contract", "session_date", "roll_session", "roll_transition", "data_condition", "is_complete"]
    if zipfile.is_zipfile(SOURCE):
        with zipfile.ZipFile(SOURCE) as z:
            csv_names = [name for name in z.namelist() if name.lower().endswith('.csv')]
            if len(csv_names) != 1:
                raise ValueError('Input ZIP must contain exactly one CSV')
            d = pd.read_csv(z.open(csv_names[0]), usecols=cols, parse_dates=["timestamp_utc"], low_memory=False)
    else:
        d = pd.read_csv(SOURCE, usecols=cols, parse_dates=["timestamp_utc"], low_memory=False)
    d = d.sort_values("timestamp_utc").reset_index(drop=True)
    assert not d.timestamp_utc.duplicated().any()
    assert d.timestamp_utc.is_monotonic_increasing
    assert np.isfinite(d[["open", "close"]].to_numpy()).all()
    d["session_date"] = d.session_date.astype(str)
    d["end"] = d.timestamp_utc + pd.Timedelta(minutes=1)
    et = d.timestamp_utc.dt.tz_convert(TZ)
    d["minute"] = et.dt.hour*60 + et.dt.minute
    quality = d.data_condition.eq("available") & d.is_complete.eq(True)
    internal_gap = d.timestamp_utc.diff().dt.total_seconds().ne(60) & d.session_date.eq(d.session_date.shift())
    reset = d.underlying_contract.ne(d.underlying_contract.shift()) | d.roll_transition | internal_gap | ~quality | ~quality.shift(fill_value=False)
    d["segment"] = reset.cumsum()
    h = aggregate(d[quality], "h", 60)
    q = aggregate(d[quality], "15min", 15)
    arrays = {k: np.full(len(d), np.nan) for k in ["trend_A", "trend_B", "mom_A", "mom_B", "conf_A", "conf_B", "trend_A_5", "trend_B_5"]}
    for seg, g in d[quality].groupby("segment", sort=False):
        p = g.index.to_numpy()
        idx = pd.DatetimeIndex(g.end)
        close = g.close
        ema = close.ewm(span=1200, adjust=False, min_periods=3600).mean()
        ema5 = close.ewm(span=1200, adjust=False, min_periods=6000).mean()
        arrays["trend_B"][p] = np.sign(ema.diff(180))
        arrays["trend_B_5"][p] = np.sign(ema5.diff(180))
        mom = close.diff(60).where(g.timestamp_utc.diff(60).dt.total_seconds().eq(3600))
        arrays["mom_B"][p] = np.sign(mom)
        hg = h[h.segment == seg].copy()
        qg = q[q.segment == seg].copy()
        if not hg.empty:
            hema = hg.close.ewm(span=20, adjust=False, min_periods=60).mean()
            ht = np.sign(hema.diff(3))
            ht5 = np.sign(hg.close.ewm(span=20, adjust=False, min_periods=100).mean().diff(3))
            arrays["trend_A"][p] = ht.reindex(idx, method="ffill")
            arrays["trend_A_5"][p] = ht5.reindex(idx, method="ffill")
            ca = pd.Series(confirmed_hourly(ht.to_numpy()), index=hg.index)
            arrays["conf_A"][p] = ca.reindex(idx, method="ffill")
        if not qg.empty:
            qm = np.sign(qg.close.diff(4)).where(qg.index.to_series().diff(4).dt.total_seconds().eq(3600))
            carried = qm.reindex(idx, method="ffill")
            last_end = pd.Series(qg.index, index=qg.index).reindex(idx, method="ffill")
            carried = carried.where((pd.Series(idx, index=idx) - last_end).dt.total_seconds().lt(900))
            arrays["mom_A"][p] = carried
        # Sample the minute trend at the same completed clock-hour boundaries.
        minute_trend = pd.Series(arrays["trend_B"][p], index=idx)
        boundary = (idx.minute == 0)
        sampled = minute_trend[boundary]
        if len(sampled):
            cb = pd.Series(confirmed_hourly(sampled.to_numpy()), index=sampled.index)
            arrays["conf_B"][p] = cb.reindex(idx, method="ffill")
    signals = {
        "A": aligned(arrays["trend_A"], arrays["mom_A"]),
        "B": aligned(arrays["trend_B"], arrays["mom_B"]),
        "C": aligned(arrays["trend_B"], arrays["mom_A"]),
        "D": aligned(arrays["trend_A"], arrays["mom_B"]),
        "A_confirm": aligned(arrays["conf_A"], arrays["mom_A"]),
        "B_confirm": aligned(arrays["conf_B"], arrays["mom_B"]),
        "trend_A": np.nan_to_num(arrays["trend_A"]).astype(np.int8),
        "trend_B": np.nan_to_num(arrays["trend_B"]).astype(np.int8),
    }
    common = quality.to_numpy() & np.isfinite(np.column_stack([arrays[k] for k in ["trend_A", "trend_B", "mom_A", "mom_B"]])).all(axis=1)
    rth = d.minute.between(570, 959)
    bad_days = d.loc[~quality, "session_date"].unique()
    rth_counts = d[rth & quality].groupby("session_date").size()
    clean_days = rth_counts[rth_counts == 390].index.difference(bad_days)
    clean = d.session_date.isin(clean_days).to_numpy()
    # The last close in a window has no following interval inside that window.
    rth_mask = common & clean & d.minute.between(569, 958).to_numpy()
    full_indicator_counts = d.loc[rth_mask].groupby('session_date').size()
    full_indicator_days = full_indicator_counts[full_indicator_counts == 390].index
    rth_mask &= d.session_date.isin(full_indicator_days).to_numpy()
    ext_mask = common & clean & ((d.minute >= 1080) | (d.minute <= 958)).to_numpy()
    selected_days = sorted(d.loc[rth_mask, "session_date"].unique())
    midpoint = selected_days[len(selected_days)//2]
    result = {"checks": {
        "source": SOURCE.name, "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "source_rows": len(d), "first_date": str(et.min().date()), "last_date": str(et.max().date()),
        "source_sessions": d.session_date.nunique(), "degraded_rows": int((~quality).sum()),
        "degraded_sessions": len(bad_days), "roll_transitions": int(d.roll_transition.sum()),
        "internal_gaps": int(internal_gap.sum()), "clean_full_rth_sessions": len(clean_days),
        "indicator_segments": int(d.segment.nunique()), "common_valid_minutes": int(common.sum()),
        "half_split_session": midpoint, "fully_warmed_rth_sessions": len(full_indicator_days),
        "hourly_vs_minute_trend_agreement_rth_pct": float((arrays["trend_A"][rth_mask] == arrays["trend_B"][rth_mask]).mean()*100),
        "signal_agreement_rth_pct": float((signals["A"][rth_mask] == signals["B"][rth_mask]).mean()*100),
    }}
    all_runs, daily_rows = [], []
    sections = {
        "primary": rth_mask, "extended": ext_mask,
        "first_half": rth_mask & (d.session_date < midpoint).to_numpy(),
        "second_half": rth_mask & (d.session_date >= midpoint).to_numpy(),
        "five_period_warmup": rth_mask & np.isfinite(arrays["trend_A_5"]) & np.isfinite(arrays["trend_B_5"]),
        "exclude_roll_sessions": rth_mask & ~d.roll_session.to_numpy(),
    }
    for section, mask in sections.items():
        result[section] = {}
        for name, sig in signals.items():
            metrics, runs = describe(sig, d, mask, name, section)
            result[section][name] = metrics
            if section in ["primary", "extended"]:
                all_runs.append(runs)
            if section == "primary":
                for day, positions in d.loc[mask].groupby("session_date").groups.items():
                    rr = runs[runs.session_date == day]
                    pp = np.asarray(list(positions))
                    daily_rows.append({"model": name, "session_date": day,
                                       "eligible_minutes": len(pp), "active_minutes": int((sig[pp] != 0).sum()),
                                       "runs": len(rr), "natural_entries": int((~rr.left_censored).sum()),
                                       "max_run_minutes": int(rr.duration_minutes.max()) if len(rr) else 0})
    # Matched-clock diagnostic: separate update cadence from different EMA inputs.
    clock_sample = d.end.dt.tz_convert(TZ).dt.minute.isin([0, 15, 30, 45]).to_numpy()
    sb = pd.Series(np.where(clock_sample, signals["B"], np.nan)).ffill().fillna(0).to_numpy(dtype=np.int8)
    result["B_quarter_hour_decisions"], _ = describe(sb, d, rth_mask, "B_quarter_hour_decisions", "primary")
    # Invariants check alignment, aggregation, and the absence of sub-quarter-hour
    # changes in A away from mask boundaries. These test the temporal mechanics.
    assert set(np.unique(signals["A"])) <= {-1, 0, 1}
    assert h["count"].eq(60).all() and q["count"].eq(15).all()
    a_changes = (signals["A"][1:] != signals["A"][:-1]) & rth_mask[1:] & rth_mask[:-1]
    assert d.end.iloc[1:][a_changes].dt.minute.isin([0, 15, 30, 45]).all()
    assert ((signals["A"] == 0) | ((signals["A"] == arrays["trend_A"]) & (signals["A"] == arrays["mom_A"]))).all()
    result["checks"]["invariants_passed"] = True
    run_export = pd.concat(all_runs, ignore_index=True)
    daily = pd.DataFrame(daily_rows)
    # A paired weekly block bootstrap checks that average run-count differences
    # are not driven by a few isolated sessions; no return-based selection.
    pair = daily.pivot(index='session_date', columns='model', values='runs')
    pair['B_minus_A'] = pair.B - pair.A
    iso = pd.to_datetime(pair.index).isocalendar()
    pair['week'] = iso.year.astype(str).to_numpy() + '-' + iso.week.astype(str).to_numpy()
    weeks = pair.groupby('week').B_minus_A.agg(['sum','count'])
    rng = np.random.default_rng(20261014)
    pick = rng.integers(0, len(weeks), size=(10000, len(weeks)))
    means = weeks['sum'].to_numpy()[pick].sum(axis=1) / weeks['count'].to_numpy()[pick].sum(axis=1)
    result['paired_weekly_bootstrap'] = {'metric': 'B minus A runs per RTH session',
        'difference': float(pair.B_minus_A.mean()), 'confidence_interval_95': np.quantile(means,[.025,.975]).tolist(), 'replicates':10000}
    for section, mask in [('primary', rth_mask), ('extended', ext_mask)]:
        for name, sig in signals.items():
            observed = int(run_export.loc[(run_export.window == section) & (run_export.model == name), 'duration_minutes'].sum())
            assert observed == int((sig[mask] != 0).sum())
    run_export.to_csv(OUT/"regime_runs.csv", index=False)
    daily.to_csv(OUT/"daily_metrics.csv", index=False)
    export = d[["timestamp_utc", "session_date", "underlying_contract", "open", "close"]].copy()
    for name, sig in signals.items():
        export[name] = sig
    export["rth_eligible"] = rth_mask
    export["extended_eligible"] = ext_mask
    export.to_csv(OUT/"minute_signals.csv.gz", index=False, compression="gzip")
    (OUT/"results.json").write_text(json.dumps(result, indent=2, allow_nan=False, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding="utf-8")
    print(json.dumps({"checks": result["checks"], "primary": result["primary"],
                      "B_quarter_hour_decisions": result["B_quarter_hour_decisions"]}, indent=2))


if __name__ == "__main__":
    main()
