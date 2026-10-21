from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


OR_LENGTHS = {"1H": [1, 2, 5], "4H": [1, 2, 5, 15, 30], "930M": [1, 2, 5, 15, 30], "1D": [1, 2, 5, 15, 30]}
ATR_LENGTHS = (9, 14)
ROUND_TURN_COST_POINTS = 0.59  # 1 tick each side plus $4.50 commission / $50 per ES point
RNG = np.random.default_rng(20261002)


def wilder(values: np.ndarray, n: int, contracts: np.ndarray) -> np.ndarray:
    out = np.full(len(values), np.nan)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and contracts[end] == contracts[start]:
            end += 1
        x = values[start:end]
        if len(x) >= n:
            out[start + n - 1] = np.mean(x[:n])
            for j in range(n, len(x)):
                out[start + j] = (out[start + j - 1] * (n - 1) + x[j]) / n
        start = end
    return out


def add_parent_ids(d: pd.DataFrame, family: str) -> pd.DataFrame:
    m = d.session_minute.to_numpy()
    if family == "1H":
        slot = m // 60
        start = slot * 60
        end = np.minimum(start + 60, 1380)
    elif family == "4H":
        slot = m // 240
        start = slot * 240
        end = np.minimum(start + 240, 1380)
    elif family == "930M":
        slot = np.zeros(len(d), dtype=int)
        start = np.zeros(len(d), dtype=int)
        end = np.full(len(d), 930)
    elif family == "1D":
        slot = np.zeros(len(d), dtype=int)
        start = np.zeros(len(d), dtype=int)
        end = np.full(len(d), 1380)
    else:
        raise ValueError(family)
    keep = (m >= start) & (m < end)
    x = d.loc[keep].copy()
    x["slot"] = slot[keep]
    x["parent_start"] = start[keep]
    x["parent_end"] = end[keep]
    x["parent_id"] = x.session_date.astype(str) + ":" + x.slot.astype(str)
    return x


def parent_table(x: pd.DataFrame) -> pd.DataFrame:
    g = x.groupby("parent_id", sort=False, observed=True)
    p = g.agg(
        session_date=("session_date", "first"),
        slot=("slot", "first"),
        start=("parent_start", "first"),
        end=("parent_end", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        first_min=("session_minute", "min"),
        last_min=("session_minute", "max"),
        count=("session_minute", "size"),
        contract=("underlying_contract", "first"),
        contract_count=("underlying_contract", "nunique"),
        any_roll=("roll_transition", "max"),
    ).reset_index()
    p["duration"] = p.end - p.start
    p["coverage"] = p["count"] / p.duration
    prev_close = p.groupby("contract", sort=False).close.shift(1)
    tr = np.maximum(p.high - p.low, np.maximum((p.high - prev_close).abs(), (p.low - prev_close).abs()))
    # First candle of a contract uses its own range, as in standard true range.
    tr = tr.fillna(p.high - p.low).to_numpy(float)
    contracts = p.contract.to_numpy()
    for n in ATR_LENGTHS:
        p[f"atr{n}"] = wilder(tr, n, contracts)
        # ATR available at the current candle open is the prior completed candle's ATR.
        p[f"atr{n}_prior"] = p.groupby("contract", sort=False)[f"atr{n}"].shift(1)
    return p


def simulate_parent(q: pd.DataFrame, meta: pd.Series, or_lengths: list[int]) -> list[dict]:
    start = int(meta.start)
    end = int(meta.end)
    if meta.contract_count != 1 or meta.coverage < 0.90 or meta.first_min != start or meta.last_min < end - 2:
        return []
    minutes = q.session_minute.to_numpy(int)
    opens = q.open.to_numpy(float)
    highs = q.high.to_numpy(float)
    lows = q.low.to_numpy(float)
    closes = q.close.to_numpy(float)
    candle_open = float(meta.open)
    minute_set = set(minutes)
    results = []
    for or_n in or_lengths:
        if not set(range(start, start + or_n)).issubset(minute_set):
            continue
        opening_mask = minutes < start + or_n
        or_hi = float(highs[opening_mask].max())
        or_lo = float(lows[opening_mask].min())
        post = np.flatnonzero(minutes >= start + or_n)
        if not len(post):
            continue
        for side in ("long", "short"):
            sweep_now = (lows[post] <= or_lo) if side == "long" else (highs[post] >= or_hi)
            swept_prior = np.r_[False, np.maximum.accumulate(sweep_now[:-1])]
            breakout = (closes[post] > or_hi) if side == "long" else (closes[post] < or_lo)
            hits = np.flatnonzero(swept_prior & breakout)
            if not len(hits):
                continue
            entry_pos = int(post[hits[0]])
            entry = float(closes[entry_pos])
            for atr_n in ATR_LENGTHS:
                atr = float(meta[f"atr{atr_n}_prior"])
                if not np.isfinite(atr) or atr <= 0:
                    continue
                stop = min(candle_open, or_hi - atr) if side == "long" else max(candle_open, or_lo + atr)
                risk = (entry - stop) if side == "long" else (stop - entry)
                if risk <= 0:
                    continue
                path = np.arange(entry_pos + 1, len(q))
                touched = (lows[path] <= stop) if side == "long" else (highs[path] >= stop)
                stop_hits = np.flatnonzero(touched)
                stopped = bool(len(stop_hits))
                exit_pos = int(path[stop_hits[0]]) if stopped else len(q) - 1
                if stopped and side == "long":
                    exit_price = float(opens[exit_pos]) if opens[exit_pos] < stop else stop
                elif stopped:
                    exit_price = float(opens[exit_pos]) if opens[exit_pos] > stop else stop
                else:
                    exit_price = float(closes[exit_pos])
                gross = (exit_price - entry) if side == "long" else (entry - exit_price)
                results.append({
                    "session_date": meta.session_date,
                    "year": pd.Timestamp(meta.session_date).year,
                    "parent_id": meta.parent_id,
                    "slot": int(meta.slot),
                    "side": side,
                    "or_minutes": or_n,
                    "atr_length": atr_n,
                    "entry_minute": int(minutes[entry_pos]),
                    "exit_minute": int(minutes[exit_pos]),
                    "entry": entry,
                    "stop": stop,
                    "exit": exit_price,
                    "risk": risk,
                    "gross_points": gross,
                    "net_points": gross - ROUND_TURN_COST_POINTS,
                    "gross_r": gross / risk,
                    "stopped": stopped,
                })
    return results

