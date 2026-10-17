"""Analyze the uploaded ES minute bars without modifying the source archive."""

from __future__ import annotations

import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ZIP_PATH = None  # Set by the portable command-line wrapper.
TIMES = ["16:00", "18:00", "00:00", "02:00", "03:00", "08:30", "09:30"]


def summarize(series: pd.Series) -> dict:
    x = series.dropna().to_numpy(dtype=float)
    n = len(x)
    if not n:
        return {"n": 0}
    sd = float(np.std(x, ddof=1)) if n > 1 else float("nan")
    return {
        "n": n,
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "sd": sd,
        "win_pct": float(np.mean(x > 0) * 100),
        "t_naive": float(np.mean(x) / (sd / math.sqrt(n))) if sd > 0 else None,
        "sum": float(np.sum(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }


def wilder_atr(true_range: pd.Series, length: int = 14) -> pd.Series:
    """Wilder ATR seeded with the first complete length-session SMA."""
    x = true_range.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    if len(x) >= length and np.isfinite(x[:length]).all():
        out[length - 1] = float(np.mean(x[:length]))
        for i in range(length, len(x)):
            out[i] = (out[i - 1] * (length - 1) + x[i]) / length if np.isfinite(x[i]) else np.nan
    return pd.Series(out, index=true_range.index)


def weekly_bootstrap(daily: pd.DataFrame, mask: pd.Series, column: str = "bps", nboot: int = 20000) -> list[float]:
    """95% percentile interval for a mean, resampling complete calendar weeks."""
    iso = pd.to_datetime(daily.index).isocalendar()
    week = iso.year.astype(str) + "-" + iso.week.astype(str)
    work = pd.DataFrame({"week": np.asarray(week), "v": np.where(np.asarray(mask), daily[column].to_numpy(), np.nan)})
    g = work.groupby("week")["v"].agg(["sum", "count"])
    rng = np.random.default_rng(20261010)
    picks = rng.integers(0, len(g), size=(nboot, len(g)))
    total = g["sum"].to_numpy()[picks].sum(axis=1)
    count = g["count"].to_numpy()[picks].sum(axis=1)
    means = total / count
    return [float(v) for v in np.quantile(means, [0.025, 0.975])]


def weekly_difference_bootstrap(daily: pd.DataFrame, mask_a: pd.Series, mask_b: pd.Series, nboot: int = 20000) -> dict:
    iso = pd.to_datetime(daily.index).isocalendar()
    week = np.asarray(iso.year.astype(str) + "-" + iso.week.astype(str))
    work = pd.DataFrame({
        "week": week,
        "a": np.where(np.asarray(mask_a), daily["bps"].to_numpy(), np.nan),
        "b": np.where(np.asarray(mask_b), daily["bps"].to_numpy(), np.nan),
    })
    g = work.groupby("week").agg({"a": ["sum", "count"], "b": ["sum", "count"]})
    rng = np.random.default_rng(20261010)
    picks = rng.integers(0, len(g), size=(nboot, len(g)))
    ma = g[("a", "sum")].to_numpy()[picks].sum(axis=1) / g[("a", "count")].to_numpy()[picks].sum(axis=1)
    mb = g[("b", "sum")].to_numpy()[picks].sum(axis=1) / g[("b", "count")].to_numpy()[picks].sum(axis=1)
    diffs = ma - mb
    return {"estimate": float(daily.loc[mask_a, "bps"].mean() - daily.loc[mask_b, "bps"].mean()), "ci95": [float(v) for v in np.quantile(diffs, [0.025, 0.975])]}


def main() -> None:
    with zipfile.ZipFile(ZIP_PATH) as z:
        df = pd.read_csv(z.open(z.namelist()[0]), parse_dates=["timestamp_utc"], low_memory=False)
    df["et"] = df["timestamp_utc"].dt.tz_convert("America/New_York")
    df["date_et"] = df["et"].dt.strftime("%Y-%m-%d")
    df["time_et"] = df["et"].dt.strftime("%H:%M")
    df["session_date"] = df["session_date"].astype(str)
    df["quality_flag"] = df["quality_flag"].fillna("")
    checks = {
        "rows": len(df),
        "first_utc": str(df["timestamp_utc"].min()),
        "last_utc": str(df["timestamp_utc"].max()),
        "duplicate_timestamps": int(df["timestamp_utc"].duplicated().sum()),
        "condition_counts": df["data_condition"].value_counts(dropna=False).to_dict(),
        "quality_counts": df["quality_flag"].value_counts(dropna=False).to_dict(),
        "complete_counts": df["is_complete"].value_counts(dropna=False).to_dict(),
        "roll_transition_counts": df["roll_transition"].value_counts(dropna=False).to_dict(),
        "date_range_et": [df["date_et"].min(), df["date_et"].max()],
        "symbols": df["underlying_contract"].value_counts().to_dict(),
        "degraded_dates": df.loc[df["data_condition"] == "degraded", "session_date"].value_counts().to_dict(),
    }

    # Minute bars are timestamped at their beginning. Their open is the price
    # available at the requested clock boundary, before that minute's movement.
    cuts = df[df["time_et"].isin(TIMES)].copy()
    cuts["key"] = cuts["time_et"]
    p = cuts.pivot_table(index="session_date", columns="key", values="open", aggfunc="first")
    contracts = cuts.pivot_table(index="session_date", columns="key", values="underlying_contract", aggfunc="first")
    counts = cuts.groupby(["session_date", "time_et"]).size().unstack(fill_value=0)
    checks["cut_presence"] = {t: int(p[t].notna().sum()) for t in TIMES}
    checks["duplicate_cuts"] = int((counts > 1).sum().sum())
    checks["session_dates"] = len(p)
    checks["cut_contract_mismatch"] = int(((contracts["18:00"] != contracts["09:30"]) & contracts["18:00"].notna() & contracts["09:30"].notna()).sum())

    daily = p.copy()
    daily["contract_entry"] = contracts["18:00"]
    daily["contract_exit"] = contracts["09:30"]
    daily = daily[daily["18:00"].notna() & daily["09:30"].notna() & (daily["contract_entry"] == daily["contract_exit"])].copy()
    daily["points"] = daily["09:30"] - daily["18:00"]
    daily["bps"] = (daily["09:30"] / daily["18:00"] - 1) * 10000
    daily["weekday"] = pd.to_datetime(daily.index).day_name()
    daily["year"] = pd.to_datetime(daily.index).year
    daily["month"] = pd.to_datetime(daily.index).to_period("M").astype(str)
    daily["half"] = np.where(pd.to_datetime(daily.index) < pd.Timestamp("2025-08-29"), "first_year", "second_year")
    for start, end in zip(TIMES[1:-1], TIMES[2:]):
        daily[f"{start}-{end}"] = daily[end] - daily[start]
    daily["02:00-03:00_bps"] = (daily["03:00"] / daily["02:00"] - 1) * 10000
    session_quality = df.groupby("session_date")["data_condition"].apply(lambda s: bool((s == "degraded").any()))
    daily["degraded"] = session_quality.reindex(daily.index).fillna(False)
    # The target interval spans 930 one-minute bars, ending at the 09:30 open.
    local_minutes = df["et"].dt.hour * 60 + df["et"].dt.minute
    overnight_bars = df[(local_minutes >= 18 * 60) | (local_minutes < 9 * 60 + 30)]
    daily["overnight_bar_count"] = overnight_bars.groupby("session_date").size().reindex(daily.index)
    daily["roll_transition"] = df.groupby("session_date")["roll_transition"].apply(lambda s: bool(s.astype(str).str.lower().eq("true").any())).reindex(daily.index).fillna(False)

    # Prior RTH session's observed price change is available before 18:00.
    rth = df[(df["time_et"] == "09:30") | (df["time_et"] == "16:00")]
    rth_p = rth.pivot_table(index="date_et", columns="time_et", values="open", aggfunc="first")
    rth_p["rth_points"] = rth_p["16:00"] - rth_p["09:30"]
    rth_p["rth_bps"] = (rth_p["16:00"] / rth_p["09:30"] - 1) * 10000
    prev_rth = rth_p[["rth_points", "rth_bps"]].shift(1)
    daily["prior_rth_points"] = prev_rth["rth_points"].reindex(daily.index)
    daily["prior_rth_bps"] = prev_rth["rth_bps"].reindex(daily.index)

    result = {"checks": checks, "overall": {"points": summarize(daily["points"]), "bps": summarize(daily["bps"])}}
    result["calendar_year"] = {str(k): summarize(g["bps"]) for k, g in daily.groupby("year")}
    result["half"] = {str(k): summarize(g["bps"]) for k, g in daily.groupby("half")}
    result["weekday"] = {str(k): summarize(g["bps"]) for k, g in daily.groupby("weekday")}
    result["weekday_points"] = {str(k): summarize(g["points"]) for k, g in daily.groupby("weekday")}
    result["nonmonday"] = {"bps": summarize(daily.loc[daily["weekday"] != "Monday", "bps"]), "points": summarize(daily.loc[daily["weekday"] != "Monday", "points"])}
    result["weekday_by_year"] = {f"{y}_{w}": summarize(g["bps"]) for (y, w), g in daily.groupby(["year", "weekday"])}
    result["month"] = {str(k): summarize(g["bps"]) for k, g in daily.groupby("month")}
    result["time_slices_points"] = {c: summarize(daily[c]) for c in daily.columns if c in [f"{a}-{b}" for a, b in zip(TIMES[1:-1], TIMES[2:])]}
    result["european_hour_bps"] = summarize(daily["02:00-03:00_bps"])
    result["prior_rth_available"] = int(daily["prior_rth_bps"].notna().sum())
    result["prior_rth_sign"] = {
        "negative": summarize(daily.loc[daily["prior_rth_bps"] < 0, "bps"]),
        "nonnegative": summarize(daily.loc[daily["prior_rth_bps"] >= 0, "bps"]),
    }
    result["prior_rth_quartile"] = {}
    eligible = daily[daily["prior_rth_bps"].notna()].copy()
    eligible["quartile"] = pd.qcut(eligible["prior_rth_bps"], 4, labels=["Q1_most_negative", "Q2", "Q3", "Q4_most_positive"])
    for k, g in eligible.groupby("quartile", observed=True):
        result["prior_rth_quartile"][str(k)] = {"prior_rth_mean_bps": float(g["prior_rth_bps"].mean()), "overnight": summarize(g["bps"])}
    eligible["abs_rth_quartile"] = pd.qcut(eligible["prior_rth_bps"].abs(), 4, labels=["Q1_small", "Q2", "Q3", "Q4_large"])
    result["prior_abs_rth_quartile"] = {str(k): summarize(g["bps"]) for k, g in eligible.groupby("abs_rth_quartile", observed=True)}
    result["cost_scenarios_points"] = {str(c): summarize(daily["points"] - c) for c in [0.5, 1.0, 2.0]}
    result["quality"] = {
        "degraded_sessions": int(daily["degraded"].sum()),
        "roll_transition_sessions": int(daily["roll_transition"].sum()),
        "overnight_bar_count": daily["overnight_bar_count"].value_counts().to_dict(),
        "degraded": summarize(daily.loc[daily["degraded"], "bps"]),
        "clean_only": summarize(daily.loc[~daily["degraded"] & ~daily["roll_transition"] & (daily["overnight_bar_count"] == 930), "bps"]),
    }
    full = pd.Series(True, index=daily.index)
    clean = ~daily["degraded"] & ~daily["roll_transition"] & (daily["overnight_bar_count"] == 930)
    result["bootstrap_ci95"] = {
        "overall_bps": weekly_bootstrap(daily, full),
        "overall_points": weekly_bootstrap(daily, full, "points"),
        "clean_bps": weekly_bootstrap(daily, clean),
        "monday_bps": weekly_bootstrap(daily, daily["weekday"] == "Monday"),
        "monday_clean_bps": weekly_bootstrap(daily, clean & (daily["weekday"] == "Monday")),
        "q1_prior_rth_bps": weekly_bootstrap(daily, daily.index.isin(eligible.index[eligible["quartile"] == "Q1_most_negative"])),
        "european_hour_bps": weekly_bootstrap(daily, full, "02:00-03:00_bps"),
        "nonmonday_bps": weekly_bootstrap(daily, daily["weekday"] != "Monday"),
    }
    result["bootstrap_differences"] = {
        "monday_vs_other": weekly_difference_bootstrap(daily, daily["weekday"] == "Monday", daily["weekday"] != "Monday"),
        "q1_vs_other": weekly_difference_bootstrap(daily, daily.index.isin(eligible.index[eligible["quartile"] == "Q1_most_negative"]), daily.index.isin(eligible.index[eligible["quartile"] != "Q1_most_negative"])),
        "second_year_vs_first": weekly_difference_bootstrap(daily, daily["half"] == "second_year", daily["half"] == "first_year"),
    }
    result["clean_monday"] = summarize(daily.loc[clean & (daily["weekday"] == "Monday"), "bps"])
    result["low_bar_sessions"] = {str(k): int(v) for k, v in daily.loc[daily["overnight_bar_count"] < 900, "overnight_bar_count"].items()}
    result["trimmed"] = {
        "mean_points_5pct_trim": float(daily["points"].sort_values().iloc[25:-25].mean()),
        "mean_bps_5pct_trim": float(daily["bps"].sort_values().iloc[25:-25].mean()),
        "exclude_2025_april_bps": summarize(daily.loc[daily["month"] != "2025-04", "bps"]),
        "monday_exclude_largest_5_absolute_bps": summarize(daily.loc[daily["weekday"] == "Monday", "bps"].iloc[np.argsort(np.abs(daily.loc[daily["weekday"] == "Monday", "bps"].to_numpy()))[:-5]]),
    }
    result["missing_pair_dates"] = sorted(set(p.index[p["18:00"].notna()]) ^ set(p.index[p["09:30"].notna()]))[:40]
    result["first_session"] = daily.index.min()
    result["last_session"] = daily.index.max()
    result["worst_sessions"] = daily["points"].nsmallest(5).to_dict()
    result["best_sessions"] = daily["points"].nlargest(5).to_dict()

    return result


if __name__ == "__main__":
    raise SystemExit("Run reproduce.py with --input and --output-dir.")
