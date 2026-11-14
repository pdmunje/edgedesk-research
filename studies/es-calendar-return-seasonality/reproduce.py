"""All declared calendar cells; anchored changes rather than price-level averages."""
from pathlib import Path
from datetime import date
from collections import defaultdict,Counter
import argparse,calendar,csv,hashlib,json,math,statistics
BASE=Path(__file__).resolve().parent

def load(path,cfg):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=cfg['input_sha256']:raise ValueError('Input fingerprint differs')
    rows=[]
    with path.open(encoding='utf-8-sig',newline='') as f:
        for x in csv.DictReader(f):
            r={'date':date.fromisoformat(x['time'])}
            for k in ('open','high','low','close'):
                r[k]=float(x[k])
                if not math.isfinite(r[k]) or r[k]<=0:raise ValueError('Invalid price')
            if not r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high']:raise ValueError('Invalid OHLC')
            if rows and r['date']<=rows[-1]['date']:raise ValueError('Duplicate/unordered date')
            if r['date'].weekday()>4:raise ValueError('Unexpected weekend date label')
            rows.append(r)
    return rows

def records(rows,cfg):
    out=[]
    for h in cfg['horizons_stored_sessions']:
        for t in range(len(rows)-h):
            b,end=rows[t],rows[t+h];entry=rows[t+1]['open']
            out.append(dict(index=t,horizon=h,start=b['date'].isoformat(),end=end['date'].isoformat(),month=b['date'].month,weekday=b['date'].weekday(),points=end['close']-b['close'],percent=100*(end['close']/b['close']-1),next_open_gross_percent=100*(end['close']-entry)/entry,next_open_cost1_percent=100*(end['close']-entry-1)/entry))
    return out

def summarize(ev,cfg):
    out=[]
    for phase in ['All','Before 2020','2020 onward']:
        for h in cfg['horizons_stored_sessions']:
            chosen=[e for e in ev if e['horizon']==h and (phase=='All' or (e['end']<cfg['split'] if phase=='Before 2020' else e['start']>=cfg['split']))]
            for family,keys in [('Baseline',[0]),('Month',list(range(1,13))),('Weekday',list(range(5)))]:
                for key in keys:
                    a=[e for e in chosen if family=='Baseline' or e['month' if family=='Month' else 'weekday']==key]
                    if not a:raise ValueError('Empty declared calendar cell')
                    out.append(dict(phase=phase,horizon=h,family=family,key=key,label='All starting dates' if family=='Baseline' else calendar.month_name[key] if family=='Month' else calendar.day_name[key],count=len(a),positive=sum(e['points']>0 for e in a),zero=sum(e['points']==0 for e in a),negative=sum(e['points']<0 for e in a),mean_percent=statistics.mean(e['percent'] for e in a),median_percent=statistics.median(e['percent'] for e in a),mean_points=statistics.mean(e['points'] for e in a),next_open_gross_mean_percent=statistics.mean(e['next_open_gross_percent'] for e in a),next_open_cost1_mean_percent=statistics.mean(e['next_open_cost1_percent'] for e in a),first_origin=min(e['start'] for e in a),last_origin=max(e['start'] for e in a)))
    return out

def calculate(path):
    cfg=json.loads((BASE/'config.json').read_text());rows=load(path,cfg);ev=records(rows,cfg);s=summarize(ev,cfg);diagnostics=[]
    for family in ['Month','Weekday']:
        early=[x for x in s if x['phase']=='Before 2020' and x['horizon']==1 and x['family']==family]
        later=[x for x in s if x['phase']=='2020 onward' and x['horizon']==1 and x['family']==family]
        best=max(early,key=lambda x:(x['mean_percent'],-x['key']));ordered=sorted(later,key=lambda x:(-x['mean_percent'],x['key']));same=next(x for x in later if x['key']==best['key'])
        diagnostics.append(dict(family=family,earlier_best=best['label'],earlier_mean_percent=best['mean_percent'],earlier_count=best['count'],later_mean_percent=same['mean_percent'],later_count=same['count'],later_rank=next(i+1 for i,x in enumerate(ordered) if x['key']==best['key']),group_count=len(early),same_sign_cells=sum((x['mean_percent']>0)==(next(z for z in later if z['key']==x['key'])['mean_percent']>0) for x in early)))
    coverage=[]
    for h in cfg['horizons_stored_sessions']:
        e=[x for x in ev if x['horizon']==h];coverage.append(dict(horizon=h,all=len(e),before=sum(x['end']<cfg['split'] for x in e),later=sum(x['start']>=cfg['split'] for x in e),cross_split=sum(x['start']<cfg['split']<=x['end'] for x in e),missing_future_rows=h))
    return dict(input=dict(rows=len(rows),first=rows[0]['date'].isoformat(),last=rows[-1]['date'].isoformat(),calendar_gap_counts=dict(Counter(str((b['date']-a['date']).days) for a,b in zip(rows,rows[1:])))),coverage=coverage,summary=s,retrospective_rank_diagnostics=diagnostics),ev

def main():
    ap=argparse.ArgumentParser();ap.add_argument('daily',type=Path);a=ap.parse_args();r,_=calculate(a.daily)
    (BASE/'results.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    with (BASE/'all-calendar-cells.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(r['summary'][0]));w.writeheader();w.writerows(r['summary'])
    print(json.dumps({'coverage':r['coverage'],'diagnostics':r['retrospective_rank_diagnostics'],'later_daily_cells':[x for x in r['summary'] if x['phase']=='2020 onward' and x['horizon']==1]},indent=2))
if __name__=='__main__':main()
