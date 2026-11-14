"""Independent Decimal forward changes and independently assembled calendar cell sums."""
from pathlib import Path
from decimal import Decimal as D
from datetime import date
from collections import defaultdict
import argparse,csv,json
from reproduce import calculate
BASE=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument('daily',type=Path);a=ap.parse_args();r,ev=calculate(a.daily)
    assert r==json.loads((BASE/'results.json').read_text())
    with a.daily.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    buckets=defaultdict(list);checked=0
    for h in [1,2,3,5,21]:
        for t in range(len(raw)-h):
            c=D(raw[t]['close']);end=D(raw[t+h]['close']);op=D(raw[t+1]['open']);dt=date.fromisoformat(raw[t]['time']);point=end-c
            vals=(100*point/c,point,100*(end-op)/op,100*(end-op-1)/op)
            phases=['All']+(['Before 2020'] if raw[t+h]['time']<'2020-01-01' else ['2020 onward'] if raw[t]['time']>='2020-01-01' else [])
            for phase in phases:
                for family,key in [('Baseline',0),('Month',dt.month),('Weekday',dt.weekday())]:buckets[(phase,h,family,key)].append(vals)
            checked+=1
    for s in r['summary']:
        a=buckets[(s['phase'],s['horizon'],s['family'],s['key'])];n=len(a)
        assert n==s['count'] and s['positive']==sum(v[1]>0 for v in a) and s['zero']==sum(v[1]==0 for v in a) and s['negative']==sum(v[1]<0 for v in a)
        for k,j in [('mean_percent',0),('mean_points',1),('next_open_gross_mean_percent',2),('next_open_cost1_mean_percent',3)]:assert abs(s[k]-float(sum(v[j] for v in a)/n))<1e-9,(k,s)
    for phase in ['All','Before 2020','2020 onward']:
        for h in [1,2,3,5,21]:
            b=next(x for x in r['summary'] if x['phase']==phase and x['horizon']==h and x['family']=='Baseline')
            for f in ['Month','Weekday']:assert sum(x['count'] for x in r['summary'] if x['phase']==phase and x['horizon']==h and x['family']==f)==b['count']
    for c in r['coverage']:assert c['before']+c['later']+c['cross_split']==c['all']==len(raw)-c['horizon']
    # Hand examples: anchor, percentage-vs-points, next-open timing and cost.
    assert D(105)-D(100)==5 and 100*(D(105)/D(100)-1)==5
    assert 100*(D(105)-D(103)-1)/D(103)==D(100)/D(103)
    # Multiplying both price marks preserves percentage, not raw point size.
    assert (D(210)/D(200)-1)==(D(105)/D(100)-1)
    out=dict(status='passed',independent_forward_windows=checked,independent_summary_cells=len(r['summary']),partition_checks=30,split_coverage_checks=5,invented_arithmetic_checks=3,scope='Summarized overlapping price-mark changes; no independent-trial inference, untouched holdout or actual fill.')
    (BASE/'verification.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
