"""Historical signal definitions; known-open ordering corrected for current results.
VWAP is an approximation from candle HLC3 and volume, not transaction VWAP.
"""
import numpy as np
import pandas as pd

def simulate_legacy(g: pd.DataFrame, idx: int, direction: int, target: float, stop: float | None) -> dict:
    entry = float(g.iloc[idx]["open"])
    ambiguous = 0
    for k in range(idx, len(g)):
        r = g.iloc[k]
        hit_target = r["low"] <= target if direction == -1 else r["high"] >= target
        hit_stop = False if stop is None else (r["high"] >= stop if direction == -1 else r["low"] <= stop)
        if hit_stop:
            ambiguous += int(hit_target)
            # A minute open beyond the stop gets the worse available opening price.
            exit_price = max(float(r["open"]), stop) if direction == -1 else min(float(r["open"]), stop)
            return {"pnl": direction * (exit_price - entry), "outcome": "stop", "exit_idx": k, "ambiguous": ambiguous}
        if hit_target:
            return {"pnl": direction * (target - entry), "outcome": "target", "exit_idx": k, "ambiguous": ambiguous}
    return {"pnl": direction * (float(g.iloc[-1]["close"]) - entry), "outcome": "time", "exit_idx": len(g)-1, "ambiguous": ambiguous}


def five_minute_bars(g: pd.DataFrame) -> pd.DataFrame:
    x = g.groupby(np.arange(len(g)) // 5).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"),
        vwap=("vwap", "last"), session_high=("session_high", "last"), session_low=("session_low", "last"),
    )
    x["vwap5"] = (((x["high"]+x["low"]+x["close"])/3)*x["volume"]).cumsum()/x["volume"].cumsum()
    x["entry_idx"] = (x.index + 1) * 5
    up_anchor = down_anchor = None
    up_run = down_run = False
    up_used = down_used = False
    previous_close = None
    bearish = []; bullish = []; short_anchors = []; long_anchors = []
    for r in x.itertuples():
        if r.close > r.open:
            if not up_run:
                up_anchor = float(r.open); up_used = False
            up_run = True
        else:
            up_run = False
        if r.close < r.open:
            if not down_run:
                down_anchor = float(r.open); down_used = False
            down_run = True
        else:
            down_run = False
        bs = up_anchor is not None and not up_used and previous_close is not None and previous_close >= up_anchor and r.close < up_anchor
        bl = down_anchor is not None and not down_used and previous_close is not None and previous_close <= down_anchor and r.close > down_anchor
        bearish.append(bool(bs)); bullish.append(bool(bl))
        short_anchors.append(up_anchor); long_anchors.append(down_anchor)
        if bs: up_used = True
        if bl: down_used = True
        previous_close = float(r.close)
    x["bearish_cisd"] = bearish; x["bullish_cisd"] = bullish
    x["short_anchor"] = short_anchors; x["long_anchor"] = long_anchors
    return x


def find_trade(g: pd.DataFrame, bars: pd.DataFrame, event: pd.Series, rule: str, scope: str) -> dict | None:
    direction = -1 if event["gap"] > 0 else 1
    target = float(event["target17"])
    gap_high = max(target, float(event["entry18"]))
    gap_low = min(target, float(event["entry18"]))
    hit = g[g["low"] <= target] if direction == -1 else g[g["high"] >= target]
    first_hit = int(hit.index[0]) if len(hit) else len(g)
    for r in bars.itertuples():
        i = int(r.entry_idx)
        if i < 30 or i >= len(g) or (scope == "overnight" and i >= 930):
            continue
        if first_hit < i:
            break
        outside = r.close > gap_high if direction == -1 else r.close < gap_low
        vw = r.close < r.vwap if direction == -1 else r.close > r.vwap
        vw5 = r.close < r.vwap5 if direction == -1 else r.close > r.vwap5
        ci = (r.bearish_cisd and r.short_anchor > gap_high) if direction == -1 else (r.bullish_cisd and r.long_anchor < gap_low)
        signal = outside and {"vwap": vw, "vwap5": vw5, "cisd": ci, "both": vw and ci}[rule]
        if not signal:
            continue
        entry = float(g.iloc[i]["open"])
        if not (entry > gap_high if direction == -1 else entry < gap_low):
            continue
        stop = float(r.session_high) + .25 if direction == -1 else float(r.session_low) - .25
        risk = abs(stop-entry)
        if risk <= 0 or not (stop > entry if direction == -1 else stop < entry):
            continue
        base = simulate(g, i, direction, target, None)
        stopped = simulate(g, i, direction, target, stop)
        before_exit = g.iloc[i:base["exit_idx"]+1]
        mae = max(0, float(before_exit["high"].max())-entry) if direction == -1 else max(0, entry-float(before_exit["low"].min()))
        return {
            "session_date": event.name, "weekday": event["weekday"], "rule": rule, "scope": scope,
            "direction": "short" if direction == -1 else "long", "entry_idx": i, "entry_time": str(g.iloc[i]["et"]),
            "signal_close": float(r.close), "signal_vwap": float(r.vwap5 if rule=="vwap5" else r.vwap), "cisd_anchor": r.short_anchor if direction == -1 else r.long_anchor,
            "entry": entry, "target": target, "stop": stop, "reward_points": abs(target-entry), "risk_points": risk,
            "reward_risk": abs(target-entry)/risk, "initial_gap": float(event["gap"]),
            "pnl_gross": base["pnl"], "pnl_net": base["pnl"]-1, "outcome": base["outcome"],
            "exit_time": str(g.iloc[base["exit_idx"]]["et"]), "holding_min_to_exit_bar": base["exit_idx"]-i,
            "mae_to_exit_bar": mae, "pnl_stop_gross": stopped["pnl"], "pnl_stop_net": stopped["pnl"]-1,
            "stop_outcome": stopped["outcome"], "ambiguous_stop_target_bar": stopped["ambiguous"],
        }
    return None


def simulate(g,idx,direction,target,stop):
    entry=float(g.iloc[idx].open)
    for k in range(idx,len(g)):
        r=g.iloc[k];opened=float(r.open)
        if stop is not None:
            if (opened < stop if direction==1 else opened > stop):
                return dict(pnl=direction*(opened-entry),outcome='stop',exit_idx=k,ambiguous=0)
            if (opened >= target if direction==1 else opened <= target):
                return dict(pnl=direction*(target-entry),outcome='target',exit_idx=k,ambiguous=0)
        ht=r.high>=target if direction==1 else r.low<=target
        hs=(r.low<=stop if direction==1 else r.high>=stop) if stop is not None else False
        if hs:return dict(pnl=direction*(stop-entry),outcome='stop',exit_idx=k,ambiguous=int(ht))
        if ht:return dict(pnl=direction*(target-entry),outcome='target',exit_idx=k,ambiguous=0)
    return dict(pnl=direction*(float(g.iloc[-1].close)-entry),outcome='time',exit_idx=len(g)-1,ambiguous=0)

