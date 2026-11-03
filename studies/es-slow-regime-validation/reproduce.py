"""Corrected recheck of a fixed slow-filter research grid; aggregate outputs only."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PACKAGE = Path(__file__).resolve().parent
HERE = PACKAGE / "results"
CFG = json.loads((PACKAGE / "analysis-config.json").read_text(encoding="utf-8"))
SRC: Path | None = None
HORIZONS = CFG["horizons"]
TICK = CFG["tick_size"]
RNG = np.random.default_rng(CFG["random_seed"])
BASELINES: dict[tuple[str, str, int, str], np.ndarray] = {}


def log(msg: str) -> None:
    print(msg, flush=True)


def rolling_sum(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    cs = np.r_[0.0, np.cumsum(x, dtype=np.float64)]
    out[n - 1 :] = cs[n:] - cs[:-n]
    return out


def rolling_sma(x: np.ndarray, n: int) -> np.ndarray:
    return rolling_sum(x, n) / n


def rolling_wma(x: np.ndarray, n: int) -> np.ndarray:
    # weights 1..n, newest bar gets n; O(N) via cumulative sums.
    out = np.full(x.size, np.nan)
    i = np.arange(1, x.size + 1, dtype=np.float64)
    cs = np.r_[0.0, np.cumsum(x, dtype=np.float64)]
    csi = np.r_[0.0, np.cumsum(x * i, dtype=np.float64)]
    end = np.arange(n, x.size + 1)
    start = end - n
    weighted = (csi[end] - csi[start]) - start * (cs[end] - cs[start])
    out[n - 1 :] = weighted / (n * (n + 1) / 2.0)
    return out


def rolling_ema(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x, copy=False).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()


def reset_by_segment(values: np.ndarray, seg: np.ndarray, n: int, kind: str) -> np.ndarray:
    out = np.full(values.size, np.nan)
    starts = np.r_[0, np.flatnonzero(seg[1:] != seg[:-1]) + 1]
    ends = np.r_[starts[1:], values.size]
    fn = {"SMA": rolling_sma, "EMA": rolling_ema, "WMA": rolling_wma}[kind]
    for a, b in zip(starts, ends):
        if b - a >= n:
            out[a:b] = fn(values[a:b], n)
    return out


def future_extreme(x: np.ndarray, h: int, maximum: bool) -> np.ndarray:
    # Monotone deque over x[t+1:t+h+1], linear time and low memory.
    n = x.size
    out = np.full(n, np.nan)
    q: deque[int] = deque()
    cmp = (lambda a, b: a >= b) if maximum else (lambda a, b: a <= b)
    for j in range(1, n):
        while q and cmp(x[j], x[q[-1]]):
            q.pop()
        q.append(j)
        t = j - h
        if t >= 0:
            while q and q[0] <= t:
                q.popleft()
            if q:
                out[t] = x[q[0]]
    return out


def qcut_edges(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    z = x[mask & np.isfinite(x)]
    return np.quantile(z, [0.2, 0.4, 0.6, 0.8])


def buckets(x: np.ndarray, edges: np.ndarray) -> np.ndarray:
    out = np.full(x.size, -1, dtype=np.int8)
    ok = np.isfinite(x)
    out[ok] = np.searchsorted(edges, x[ok], side="right").astype(np.int8) + 1
    return out


def period_mask(labels: np.ndarray, name: str) -> np.ndarray:
    return labels == name


def metric_arrays(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {c: df[c].to_numpy() for c in df.columns if c.startswith(("long_", "short_", "tf_"))}


def matched_baseline(metric: np.ndarray, mask: np.ndarray, minute: np.ndarray) -> tuple[np.ndarray, float]:
    ok = mask & np.isfinite(metric)
    sums = np.bincount(minute[ok], weights=metric[ok], minlength=1380)
    cnts = np.bincount(minute[ok], minlength=1380)
    lookup = np.divide(sums, cnts, out=np.full(1380, np.nan), where=cnts > 0)
    return lookup, float(np.nanmean(metric[ok]))


def summarize_state(name: str, family: str, ma_type: str, length: int, slope_h: int,
                    state: str, smask: np.ndarray, eval_mask: np.ndarray, period: str,
                    minute: np.ndarray, day: np.ndarray, year: np.ndarray,
                    arr: dict[str, np.ndarray], side_filter: str | None = None) -> list[dict]:
    m = smask & eval_mask
    rows = []
    coverage = 100.0 * m.sum() / max(1, eval_mask.sum())
    for side in ("long", "short"):
        if side_filter and side != side_filter:
            continue
        for h in HORIZONS:
            ret = arr[f"{side}_return_{h}"]
            good = m & np.isfinite(ret)
            base_lookup = BASELINES[(period,side,h,"ret")]
            base_vals = base_lookup[minute[good]]
            pos = (ret > 0).astype(float)
            pos_lookup = BASELINES[(period,side,h,"pos")]
            p = float(np.mean(pos[good])) if good.any() else np.nan
            bp = float(np.nanmean(pos_lookup[minute[good]])) if good.any() else np.nan
            mean = float(np.mean(ret[good])) if good.any() else np.nan
            bm = float(np.nanmean(base_vals)) if good.any() else np.nan
            mfe = arr[f"{side}_MFE_{h}"]
            mae = arr[f"{side}_MAE_{h}"]
            tf = arr[f"tf_{side}_{h}"]
            rows.append({
                "candidate": name, "family": family, "ma_type": ma_type, "length": length,
                "slope_horizon": slope_h, "period": period, "direction": side.upper(),
                "horizon": h, "state": state, "coverage_pct": coverage,
                "raw_observations": int(good.sum()), "distinct_trading_days": int(np.unique(day[good]).size),
                "distinct_years": int(np.unique(year[good]).size), "positive_pct": 100*p,
                "matched_baseline_positive_pct": 100*bp, "excess_positive_pp": 100*(p-bp),
                "mean_return_pct": 100*mean, "matched_baseline_mean_return_pct": 100*bm,
                "excess_mean_return_bp": 10000*(mean-bm),
                "mean_MFE_points": float(np.nanmean(mfe[good])) if good.any() else np.nan,
                "mean_MAE_points": float(np.nanmean(mae[good])) if good.any() else np.nan,
                "target_first_pct": 100*float(np.nanmean(tf[good] == 1)) if good.any() else np.nan,
                "stop_first_pct": 100*float(np.nanmean(tf[good] == -1)) if good.any() else np.nan,
                "unresolved_or_no_touch_pct": 100*float(np.nanmean(tf[good] == 0)) if good.any() else np.nan,
            })
    return rows


def bucket_excesses(score: np.ndarray, edges: np.ndarray, emask: np.ndarray, side: str, h: int,
                    minute: np.ndarray, arr: dict[str,np.ndarray], period_name: str) -> np.ndarray:
    b=buckets(score,edges); ret=arr[f"{side}_return_{h}"]; base=BASELINES[(period_name,side,h,"ret")]
    ok=emask&np.isfinite(ret)&(b>0); ex=ret[ok]-base[minute[ok]]; bb=b[ok]
    sums=np.bincount(bb,weights=ex,minlength=6); cnt=np.bincount(bb,minlength=6)
    return np.divide(sums[1:6],cnt[1:6],out=np.full(5,np.nan),where=cnt[1:6]>0)*10000


def monotonic_label(vals: np.ndarray, increasing: bool = True) -> tuple[float, str]:
    x = np.arange(vals.size)
    ok = np.isfinite(vals)
    if ok.sum() < 3:
        return np.nan, "insufficient"
    rho = float(np.corrcoef(x[ok], vals[ok])[0, 1])
    if not increasing:
        rho = -rho
    dif = np.diff(vals)
    correct = np.mean(dif >= 0) if increasing else np.mean(dif <= 0)
    label = "clear" if rho >= .9 and correct >= .75 else "approximate" if rho >= .6 else "weak" if rho >= .25 else "non-monotonic"
    return rho, label


def rolling_regression(y: np.ndarray, seg: np.ndarray, n: int) -> tuple[np.ndarray, ...]:
    slope = np.full(y.size, np.nan); fit = slope.copy(); r2 = slope.copy(); resid = slope.copy(); quality = slope.copy()
    sx = n*(n-1)/2.0; sxx = n*(n-1)*(2*n-1)/6.0 - sx*sx/n
    starts = np.r_[0, np.flatnonzero(seg[1:] != seg[:-1]) + 1]; ends = np.r_[starts[1:], y.size]
    for a,b in zip(starts, ends):
        z=y[a:b]
        if z.size < n: continue
        sy=rolling_sum(z,n); sy2=rolling_sum(z*z,n); iy=rolling_sum(z*np.arange(1,z.size+1),n)
        end=np.arange(n,z.size+1); start=end-n
        sxy=iy[n-1:] - (start+1)*sy[n-1:]
        sl=(sxy-sx*sy[n-1:]/n)/sxx
        mean=sy[n-1:]/n; sst=np.maximum(sy2[n-1:]-sy[n-1:]**2/n,0)
        explained=sl*sl*sxx; sse=np.maximum(sst-explained,0)
        rs=np.sqrt(sse/n); rr=np.divide(explained,sst,out=np.zeros_like(sl),where=sst>0)
        idx=np.arange(a+n-1,b)
        slope[idx]=sl; fit[idx]=mean+sl*(n-1)/2; r2[idx]=rr; resid[idx]=rs
        quality[idx]=np.divide(sl*(n-1),rs,out=np.full_like(sl,np.nan),where=rs>0)
    return slope,fit,r2,resid,quality


def full_distribution(label: str, smask: np.ndarray, emask: np.ndarray, side: str, h: int,
                      minute: np.ndarray, day: np.ndarray, year: np.ndarray, arr: dict[str,np.ndarray]) -> dict:
    ret=arr[f"{side}_return_{h}"]; mfe=arr[f"{side}_MFE_{h}"]; mae=arr[f"{side}_MAE_{h}"]; tf=arr[f"tf_{side}_{h}"]
    m=smask&emask&np.isfinite(ret); base,_=matched_baseline(ret,emask,minute); excess=ret[m]-base[minute[m]]
    pos=(ret>0).astype(float); pbase,_=matched_baseline(pos,emask&np.isfinite(ret),minute)
    # Day-block bootstrap of day-balanced mean excess.
    d=day[m]; u,inv=np.unique(d,return_inverse=True); sums=np.bincount(inv,weights=excess); cnt=np.bincount(inv); daily=sums/cnt
    boots=np.mean(daily[RNG.integers(0,len(daily),(CFG["bootstrap_repetitions"],len(daily)))],axis=1) if len(daily) else np.array([np.nan])
    q=np.nanquantile(ret[m],[.1,.25,.5,.75,.9]) if m.any() else [np.nan]*5
    return {"candidate":label,"period":"","direction":side.upper(),"horizon":h,"raw_observations":int(m.sum()),
            "distinct_trading_days":len(u),"distinct_years":int(np.unique(year[m]).size),"positive_pct":100*np.mean(ret[m]>0),
            "matched_baseline_positive_pct":100*np.nanmean(pbase[minute[m]]),"excess_positive_pp":100*(np.mean(ret[m]>0)-np.nanmean(pbase[minute[m]])),
            "mean_return_pct":100*np.mean(ret[m]),"median_return_pct":100*q[2],"p10_return_pct":100*q[0],"p25_return_pct":100*q[1],
            "p75_return_pct":100*q[3],"p90_return_pct":100*q[4],"mean_MFE_points":np.mean(mfe[m]),"median_MFE_points":np.median(mfe[m]),
            "mean_MAE_points":np.mean(mae[m]),"median_MAE_points":np.median(mae[m]),"MFE_MAE_ratio":np.mean(mfe[m])/np.mean(mae[m]),
            "target_first_pct":100*np.mean(tf[m]==1),"stop_first_pct":100*np.mean(tf[m]==-1),"unresolved_or_no_touch_pct":100*np.mean(tf[m]==0),
            "matched_excess_mean_bp":10000*np.mean(excess),"day_balanced_mean_excess_bp":10000*np.mean(daily),"day_block_ci_low_bp":10000*np.quantile(boots,.025),"day_block_ci_high_bp":10000*np.quantile(boots,.975)}


def make_target_stop_diagnostics(directory: Path) -> None:
    """Primary-stack target/stop diagnostics with minute-matched target baselines."""
    t=read_source(["timestamp_utc","high","low","close","roll_transition","is_complete"]); ts=pd.DatetimeIndex(t.timestamp_utc);local=ts.tz_convert("America/New_York")
    minute=((local.hour.to_numpy()-18)%24)*60+local.minute.to_numpy();d=(local.normalize()+pd.to_timedelta((local.hour>=18).astype(int),unit="D")).date;day=np.array(d);year=np.array([x.year for x in day])
    labels=np.full(len(t),"OTHER",object);labels[(year>=2010)&(year<=2014)]="HISTORICAL_ROBUSTNESS";labels[(year>=2015)&(year<=2022)]="DISCOVERY";labels[(year>=2023)&(year<=2024)]="VALIDATION";labels[year>=2025]="HOLDOUT"
    close=t.close.to_numpy(float);high=t.high.to_numpy(float);low=t.low.to_numpy(float);seg=t.source_roll_segment.to_numpy(); sh=CFG["stack_slope_horizon"]
    mas=[reset_by_segment(close,seg,L,"EMA") for L in CFG["primary_stack"]];slopes=[]
    for ma in mas:
        x=np.full(len(t),np.nan);same=np.r_[np.zeros(sh,dtype=bool),seg[sh:]==seg[:-sh]];x[sh:]=ma[sh:]-ma[:-sh];x[~same]=np.nan;slopes.append(x)
    bull=sum([(close>m).astype(np.int8) for m in mas])+sum([(mas[i]>mas[i+1]).astype(np.int8) for i in range(2)])+sum([(x>0).astype(np.int8) for x in slopes])
    bear=sum([(close<m).astype(np.int8) for m in mas])+sum([(mas[i]<mas[i+1]).astype(np.int8) for i in range(2)])+sum([(x<0).astype(np.int8) for x in slopes]);signed=bull-bear
    stack_valid=np.all(np.isfinite(np.vstack(mas+slopes)),axis=0)
    states={"strong_bearish":(bear>=7)&stack_valid,"neutral":(np.abs(signed)<=1)&stack_valid,"strong_bullish":(bull>=7)&stack_valid};flags={}
    for h in HORIZONS:
        same=np.r_[seg[h:]==seg[:-h],np.zeros(h,dtype=bool)];same_period=np.r_[labels[h:]==labels[:-h],np.zeros(h,dtype=bool)];ok=same&same_period&(minute<1380);fmax=future_extreme(high,h,True);fmin=future_extreme(low,h,False)
        for side in ("long","short"):
            mfe=fmax-close if side=="long" else close-fmin;mae=close-fmin if side=="long" else fmax-close;rt=(mfe>=8)&ok;rs=(mae>=6.25)&ok
            out=np.zeros(len(t),dtype=np.int8);out[rt&~rs]=1;out[rs&~rt]=-1;active=rt&rs;target=close+(8 if side=="long" else -8);stop=close+(-6.25 if side=="long" else 6.25)
            for k in range(1,h+1):
                idx=np.flatnonzero(active[:-k]);fi=idx+k;ht=(high[fi]>=target[idx]) if side=="long" else (low[fi]<=target[idx]);hs=(low[fi]<=stop[idx]) if side=="long" else (high[fi]>=stop[idx]);out[idx[ht&~hs]]=1;out[idx[hs&~ht]]=-1;active[idx[ht|hs]]=False
            out[~ok]=2;flags[(side,h)]=out
    rows=[]
    for pn in ("DISCOVERY","VALIDATION","HOLDOUT","HISTORICAL_ROBUSTNESS"):
        em=labels==pn
        for side in ("long","short"):
            for h in HORIZONS:
                f=flags[(side,h)];eligible=em&(f!=2);base,_=matched_baseline((f==1).astype(float),eligible,minute)
                for state,sm in states.items():
                    m=sm&eligible;raw=np.mean(f[m]==1);mb=np.nanmean(base[minute[m]])
                    rows.append({"period":pn,"state":state,"direction":side.upper(),"horizon":h,"observations":int(m.sum()),"coverage_pct":100*m.sum()/eligible.sum(),"target_first_pct":100*raw,"matched_baseline_target_first_pct":100*mb,"excess_target_first_pp":100*(raw-mb),"stop_first_pct":100*np.mean(f[m]==-1),"unresolved_or_no_touch_pct":100*np.mean(f[m]==0)})
    pd.DataFrame(rows).to_csv(directory/"target_stop_diagnostics.csv",index=False,float_format="%.10g")


def read_source(columns: list[str]) -> pd.DataFrame:
    frame=pq.read_table(SRC,columns=columns).to_pandas().sort_values("timestamp_utc",kind="stable")
    frame=frame.loc[frame.is_complete.fillna(False)].reset_index(drop=True)
    assert not frame.timestamp_utc.duplicated().any()
    frame["source_roll_segment"]=np.cumsum(frame.roll_transition.fillna(False).to_numpy(bool)).astype(np.int32)
    local=pd.DatetimeIndex(frame.timestamp_utc).tz_convert("America/New_York")
    minute=((local.hour.to_numpy()-18)%24)*60+local.minute.to_numpy()
    original={"complete_source_rows":len(frame),"first_timestamp_utc":str(frame.timestamp_utc.min()),"last_timestamp_utc":str(frame.timestamp_utc.max()),"maintenance_rows_removed":int((minute>=1380).sum()),"roll_transitions_before_removal":int(frame.roll_transition.sum())}
    for field in ["price_source","volume_source","quality_state"]:
        if field in frame:original[field+"_counts"]=frame[field].value_counts().to_dict()
    frame=frame.loc[minute<1380].reset_index(drop=True)
    for field in ["open","high","low","close"]:
        if field in frame:assert np.isfinite(frame[field]).all() and frame[field].gt(0).all()
    if all(field in frame for field in ["open","high","low","close"]):assert (frame.low<=frame[["open","close"]].min(axis=1)).all() and (frame.high>=frame[["open","close"]].max(axis=1)).all()
    frame.attrs["original_audit"]=original
    return frame


def main() -> None:
    global SRC,HERE
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--input",required=True,type=Path);parser.add_argument("--output",type=Path,default=HERE);args=parser.parse_args();SRC=args.input;HERE=args.output;HERE.mkdir(parents=True,exist_ok=True)
    assert hashlib.sha256(SRC.read_bytes()).hexdigest()==CFG["source_sha256"],"Source fingerprint differs; do not silently substitute input"
    log("Reading licensed minute source...")
    cols=["timestamp_utc","open","high","low","close","volume","underlying_contract","price_source","volume_source","quality_state","roll_session","roll_transition","is_complete"]
    df=read_source(cols)
    ts=pd.DatetimeIndex(df.timestamp_utc); local=ts.tz_convert("America/New_York")
    minute=((local.hour.to_numpy()-18)%24)*60+local.minute.to_numpy(); session_date=(local.normalize()+pd.to_timedelta((local.hour>=18).astype(int),unit="D")).date
    # Integer day keys preserve date grouping/order while avoiding repeated object-date sorts.
    day=np.array(session_date,dtype='datetime64[D]').astype(np.int64); year=np.array([d.year for d in session_date],dtype=np.int16)
    period=np.full(len(df),"OTHER",object); period[(year>=2010)&(year<=2014)]="HISTORICAL_ROBUSTNESS"; period[(year>=2015)&(year<=2022)]="DISCOVERY"; period[(year>=2023)&(year<=2024)]="VALIDATION"; period[year>=2025]="HOLDOUT"
    close=df.close.to_numpy(float); high=df.high.to_numpy(float); low=df.low.to_numpy(float)
    seg=df.source_roll_segment.to_numpy(dtype=np.int32)
    valid=np.isfinite(close)&np.isfinite(high)&np.isfinite(low)&(minute>=0)&(minute<1380)
    audit={"source_file":SRC.name,"sha256":hashlib.sha256(SRC.read_bytes()).hexdigest(),"rows":len(df),"first_timestamp_utc":str(ts.min()),"last_timestamp_utc":str(ts.max()),
           "timezone":"UTC (session labels America/New_York)","fields":cols,"duplicate_timestamps":int(ts.duplicated().sum()),"roll_transitions":int(df.roll_transition.sum()),
           "price_sources":df.price_source.value_counts().to_dict(),"volume_sources":df.volume_source.value_counts().to_dict(),"quality_states":df.quality_state.value_counts().to_dict(),
           "eligible_session_rows":int(valid.sum()),"maintenance_window_rows_excluded":df.attrs["original_audit"]["maintenance_rows_removed"],
           "session_minute_coverage":int(np.unique(minute[minute<1380]).size),"session_bar_count_distribution":pd.Series(day[minute<1380]).value_counts().describe().to_dict()}
    audit["original_audit"]=df.attrs["original_audit"]
    # Gap audit: only within expected Sun-Fri session clock, recorded separately from bar-count calculations.
    minute_stamp=ts.to_numpy(dtype="datetime64[m]").astype("int64")
    delta=np.diff(minute_stamp); audit["timestamp_gaps_over_1m"]=int(np.sum(delta>1)); audit["largest_gap_minutes"]=int(delta.max()); audit["missing_wallclock_minutes_between_observations"]=int(np.sum(np.maximum(delta-1,0)))
    (HERE/"data_audit.json").write_text(json.dumps(audit,indent=2,default=str),encoding="utf-8")
    arr={}
    log("Computing forward outcomes...")
    for h in HORIZONS:
        same=np.r_[seg[h:]==seg[:-h],np.zeros(h,dtype=bool)]
        fc=np.r_[close[h:],np.full(h,np.nan)]; fmax=future_extreme(high,h,True); fmin=future_extreme(low,h,False)
        same_period=np.r_[period[h:]==period[:-h],np.zeros(h,dtype=bool)]
        ok=valid&same&same_period&np.isfinite(fc)&np.isfinite(fmax)&np.isfinite(fmin)
        for side in ("long","short"):
            sign=1 if side=="long" else -1
            ret=sign*(fc-close)/close; mfe=(fmax-close) if side=="long" else (close-fmin); mae=(close-fmin) if side=="long" else (fmax-close)
            mfe=np.maximum(mfe,0);mae=np.maximum(mae,0)
            ret[~ok]=np.nan;mfe[~ok]=np.nan;mae[~ok]=np.nan
            arr[f"{side}_return_{h}"]=ret;arr[f"{side}_MFE_{h}"]=mfe;arr[f"{side}_MAE_{h}"]=mae
        # Exact target-first diagnostic. Extrema settle one-barrier and neither cases;
        # only paths touching both barriers require an ordered scan.
        for side in ("long","short"):
            out=np.zeros(len(df),dtype=np.int8); target=close+(8 if side=="long" else -8); stop=close+(-6.25 if side=="long" else 6.25)
            reach_t=(arr[f"{side}_MFE_{h}"]>=8)&ok; reach_s=(arr[f"{side}_MAE_{h}"]>=6.25)&ok
            out[reach_t&~reach_s]=1; out[reach_s&~reach_t]=-1; active=reach_t&reach_s
            for k in range(1,h+1):
                idx=np.flatnonzero(active[:-k]); future_idx=idx+k
                hit_t=(high[future_idx]>=target[idx]) if side=="long" else (low[future_idx]<=target[idx])
                hit_s=(low[future_idx]<=stop[idx]) if side=="long" else (high[future_idx]>=stop[idx])
                # Ambiguous same-bar hits are classified neither (unknown intrabar order).
                only_t=hit_t&~hit_s; only_s=hit_s&~hit_t
                out[idx[only_t]]=1;out[idx[only_s]]=-1;active[idx[hit_t|hit_s]]=False
            out[~ok]=2;arr[f"tf_{side}_{h}"]=out
    discovery=period=="DISCOVERY"; validation=period=="VALIDATION"; prehold=discovery|validation
    for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation),("HOLDOUT",period=="HOLDOUT"),("HISTORICAL_ROBUSTNESS",period=="HISTORICAL_ROBUSTNESS")):
        for side in ("long","short"):
            for h in HORIZONS:
                ret=arr[f"{side}_return_{h}"]; BASELINES[(pname,side,h,"ret")]=matched_baseline(ret,emask,minute)[0]
                BASELINES[(pname,side,h,"pos")]=matched_baseline((ret>0).astype(float),emask&np.isfinite(ret),minute)[0]
    candidate_rows=[]; mono_rows=[]; feature_cache={}
    log("Evaluating moving-average level and slope families...")
    for typ in CFG["ma_types"]:
        for L in CFG["ma_lengths"]:
            ma=reset_by_segment(close,seg,L,typ); dist=(close-ma)/close
            if typ=="EMA" and L in set(CFG["primary_stack"]+CFG["secondary_stack"]): feature_cache[(typ,L)]=ma.copy()
            edges=qcut_edges(dist,discovery&valid); qb=buckets(dist,edges)
            for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation)):
                for state,sm in (("above",close>ma),("below",close<ma)):
                    candidate_rows+=summarize_state(f"{typ}{L}_{state}","price_vs_ma",typ,L,0,state,sm,emask,pname,minute,day,year,arr)
                # Tail details are in the wide candidate table; all five bucket
                # means and monotonicity classifications are emitted separately.
                candidate_rows+=summarize_state(f"{typ}{L}_distance_Q1","distance_bucket",typ,L,0,"Q1",qb==1,emask,pname,minute,day,year,arr,"short")
                candidate_rows+=summarize_state(f"{typ}{L}_distance_Q5","distance_bucket",typ,L,0,"Q5",qb==5,emask,pname,minute,day,year,arr,"long")
            for side,h in (("LONG",60),("LONG",240),("SHORT",60),("SHORT",240)):
                vals=bucket_excesses(dist,edges,validation,side.lower(),h,minute,arr,"VALIDATION")
                rho,lab=monotonic_label(np.array(vals),increasing=side=="LONG")
                mono_rows.append({"candidate":f"{typ}{L}_distance","family":"distance_bucket","direction":side,"horizon":h,"period":"VALIDATION","bucket_index_correlation":rho,"classification":lab,**{f"Q{i+1}_excess_bp":v for i,v in enumerate(vals)}})
            for sh in CFG["slope_horizons"]:
                sl=np.full(len(df),np.nan); same=np.r_[np.zeros(sh,dtype=bool),seg[sh:]==seg[:-sh]]; sl[sh:]=(ma[sh:]-ma[:-sh])/close[sh:]/sh; sl[~same]=np.nan
                sedges=qcut_edges(sl,discovery&valid); sb=buckets(sl,sedges)
                for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation)):
                    conditions=(("bull",(close>ma)&(sl>0)),("bear",(close<ma)&(sl<0)))
                    for state,sm in conditions:
                        intended="long" if state=="bull" else "short"
                        candidate_rows+=summarize_state(f"{typ}{L}_slope{sh}_{state}","ma_level_slope",typ,L,sh,state,sm,emask,pname,minute,day,year,arr,intended)
                for side,h in (("LONG",60),("LONG",240),("SHORT",60),("SHORT",240)):
                    vals=bucket_excesses(sl,sedges,validation,side.lower(),h,minute,arr,"VALIDATION")
                    rho,lab=monotonic_label(vals,increasing=side=="LONG")
                    mono_rows.append({"candidate":f"{typ}{L}_slope{sh}","family":"slope_bucket","direction":side,"horizon":h,"period":"VALIDATION","bucket_index_correlation":rho,"classification":lab,**{f"Q{i+1}_excess_bp":v for i,v in enumerate(vals)}})
                del sl,sb
            del ma,dist,qb; gc.collect()
    log("Evaluating rolling regressions...")
    for L in CFG["regression_lengths"]:
        sl,fit,r2,resid,quality=rolling_regression(close,seg,L); edges=qcut_edges(quality,discovery&valid); qb=buckets(quality,edges)
        for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation)):
            # Detailed tail states; all five buckets remain in bucket_monotonicity.csv.
            for b in (1,5):
                intended="short" if b==1 else "long"
                candidate_rows+=summarize_state(f"OLS{L}_quality_Q{b}","rolling_regression","OLS",L,0,f"Q{b}",qb==b,emask,pname,minute,day,year,arr,intended)
        for side,h in (("LONG",60),("LONG",240),("SHORT",60),("SHORT",240)):
            vals=bucket_excesses(quality,edges,validation,side.lower(),h,minute,arr,"VALIDATION")
            rho,lab=monotonic_label(np.array(vals),increasing=side=="LONG")
            mono_rows.append({"candidate":f"OLS{L}_quality","family":"rolling_regression","direction":side,"horizon":h,"period":"VALIDATION","bucket_index_correlation":rho,"classification":lab,**{f"Q{i+1}_excess_bp":v for i,v in enumerate(vals)}})
        del sl,fit,r2,resid,quality,qb;gc.collect()
    log("Evaluating EMA stack structures...")
    stack_masks={}; stack_scores={}
    for stack_name,lens in (("primary",CFG["primary_stack"]),("secondary",CFG["secondary_stack"])):
        mas=[feature_cache[("EMA",L)] for L in lens]; slopes=[]; sh=CFG["stack_slope_horizon"]
        for ma in mas:
            x=np.full(len(df),np.nan); same=np.r_[np.zeros(sh,dtype=bool),seg[sh:]==seg[:-sh]];x[sh:]=ma[sh:]-ma[:-sh];x[~same]=np.nan;slopes.append(x)
        bull=sum([(close>m).astype(np.int8) for m in mas])+sum([(mas[i]>mas[i+1]).astype(np.int8) for i in range(2)])+sum([(x>0).astype(np.int8) for x in slopes])
        bear=sum([(close<m).astype(np.int8) for m in mas])+sum([(mas[i]<mas[i+1]).astype(np.int8) for i in range(2)])+sum([(x<0).astype(np.int8) for x in slopes])
        signed=bull-bear; stack_scores[stack_name]=(bull,bear,signed)
        stack_valid=np.all(np.isfinite(np.vstack(mas+slopes)),axis=0)
        for score_name,score,direction in (("bullish",bull,"LONG"),("bearish",bear,"SHORT"),("signed",signed,"LONG")):
            vals_by_h={60:[],240:[]}; levels=range(-8,9) if score_name=="signed" else range(0,9)
            for level in levels:
                for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation)):
                    candidate_rows+=summarize_state(f"{stack_name}_{score_name}_score_{level}","stack", "EMA",lens[-1],sh,str(level),(score==level)&stack_valid,emask,pname,minute,day,year,arr)
                for h in HORIZONS:
                    rr=[r for r in candidate_rows if r["candidate"]==f"{stack_name}_{score_name}_score_{level}" and r["period"]=="VALIDATION" and r["direction"]==direction and r["horizon"]==h]
                    vals_by_h[h].append(rr[-1]["excess_mean_return_bp"] if rr else np.nan)
            for h,vals in vals_by_h.items():
                rho,lab=monotonic_label(np.array(vals),increasing=True)
                mono_rows.append({"candidate":f"{stack_name}_{score_name}_score","family":"stack","direction":direction,"horizon":h,"period":"VALIDATION","bucket_index_correlation":rho,"classification":lab})
        stack_masks[f"{stack_name}_strong_bull"]=(bull>=7)&stack_valid;stack_masks[f"{stack_name}_strong_bear"]=(bear>=7)&stack_valid;stack_masks[f"{stack_name}_neutral"]=(np.abs(signed)<=1)&stack_valid
    candidates=pd.DataFrame(candidate_rows); candidates.to_csv(HERE/"candidate_summary.csv",index=False,float_format="%.10g")
    pd.DataFrame(mono_rows).to_csv(HERE/"bucket_monotonicity.csv",index=False,float_format="%.10g")
    # Reuse the four earlier diagnostic rules; do not select from this rerun.
    frozen=json.loads((PACKAGE/"frozen-definitions.json").read_text(encoding="utf-8"))
    for key,spec in frozen.items():
        side="LONG" if key.startswith("long") else "SHORT";h=int(key.split("_")[1])
        for period_name,field in [("DISCOVERY","discovery_excess_bp"),("VALIDATION","validation_excess_bp")]:
            match=candidates[(candidates.candidate==spec["candidate"])&(candidates.direction==side)&(candidates.horizon==h)&(candidates.period==period_name)]
            assert len(match)==1
            spec[field]=float(match.excess_mean_return_bp.iloc[0])
    (HERE/"frozen_candidates.json").write_text(json.dumps(frozen,indent=2),encoding="utf-8")
    log("Earlier rules fixed; rechecking already examined later and historical periods...")
    final_masks={}
    for key,spec in frozen.items():
        typ,L,sh=spec["ma_type"],spec["length"],spec["slope_horizon"]
        ma=reset_by_segment(close,seg,L,typ); sl=np.full(len(df),np.nan);same=np.r_[np.zeros(sh,dtype=bool),seg[sh:]==seg[:-sh]];sl[sh:]=ma[sh:]-ma[:-sh];sl[~same]=np.nan
        final_masks[key]=((close>ma)&(sl>0)) if key.startswith("long") else ((close<ma)&(sl<0))
    # Full final distributions and cross-checks.
    long_rows=[];short_rows=[];hold_rows=[];hist_rows=[]
    for key,sm in final_masks.items():
        intended_side="long" if key.startswith("long") else "short"; h=int(key.split("_")[1])
        for pname,emask in (("DISCOVERY",discovery),("VALIDATION",validation),("HOLDOUT",period=="HOLDOUT"),("HISTORICAL_ROBUSTNESS",period=="HISTORICAL_ROBUSTNESS")):
            for side in ("long","short"):
                r=full_distribution(key,sm,emask,side,h,minute,day,year,arr);r["period"]=pname
                (long_rows if intended_side=="long" else short_rows).append(r)
                if pname=="HOLDOUT":hold_rows.append(r)
                if pname=="HISTORICAL_ROBUSTNESS":hist_rows.append(r)
    pd.DataFrame(long_rows).to_csv(HERE/"long_regime_results.csv",index=False,float_format="%.10g");pd.DataFrame(short_rows).to_csv(HERE/"short_regime_results.csv",index=False,float_format="%.10g")
    pd.DataFrame(hold_rows).to_csv(HERE/"holdout_results.csv",index=False,float_format="%.10g");pd.DataFrame(hist_rows).to_csv(HERE/"historical_robustness.csv",index=False,float_format="%.10g")
    # Annual and requested subperiod stability for intended side, plus structural states.
    annual=[];period_rows=[]
    for key,sm in {**final_masks,**stack_masks}.items():
        side="long" if ("long" in key or "bull" in key) else "short"; hs=HORIZONS if key.startswith(("primary","secondary")) else [int(key.split("_")[1])]
        for h in hs:
            for yy in sorted(np.unique(year)):
                if yy<2010:continue
                r=full_distribution(key,sm,year==yy,side,h,minute,day,year,arr);r["year"]=yy;annual.append(r)
            groups={"2015-2017":(year>=2015)&(year<=2017),"2018-2019":(year>=2018)&(year<=2019),"2020":year==2020,"2021-2022":(year>=2021)&(year<=2022),"2023-2024":(year>=2023)&(year<=2024),"2025-latest":year>=2025}
            for pn,em in groups.items():
                r=full_distribution(key,sm,em,side,h,minute,day,year,arr);r["subperiod"]=pn;period_rows.append(r)
    pd.DataFrame(annual).to_csv(HERE/"annual_stability.csv",index=False,float_format="%.10g");pd.DataFrame(period_rows).to_csv(HERE/"period_stability.csv",index=False,float_format="%.10g")
    make_target_stop_diagnostics(HERE)
    assert hashlib.sha256(SRC.read_bytes()).hexdigest()==CFG["source_sha256"]
    log("Complete: fixed rules and full aggregate grid recalculated; no publication.")



if __name__ == "__main__":
    main()
