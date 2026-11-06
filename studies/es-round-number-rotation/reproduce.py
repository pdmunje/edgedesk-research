"""First-touch two-sided extent and same-day/time/prior-range shifted controls."""
import argparse,csv,datetime as dt,hashlib,json,math
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
P=Path(__file__).resolve().parent
C=json.loads((P/'config.json').read_text(encoding='utf-8'))

def level_class(k):return '100' if k%4==0 else '50-only' if k%2==0 else '25-only'

def load(path):
    before=hashlib.sha256(path.read_bytes()).hexdigest();assert before==C['source_sha256'],'Unexpected input fingerprint'
    raw=list(csv.DictReader(path.open(encoding='utf-8-sig')));groups={};seen=set();previous=None
    for row in raw:
        time=dt.datetime.fromisoformat(row['time']);assert time.tzinfo is not None;utc=time.astimezone(dt.timezone.utc);assert utc not in seen and (previous is None or utc>previous),'Duplicate/unordered timestamp';seen.add(utc);previous=utc;local=time.astimezone(ZoneInfo(C['timezone']));v={k:float(row[k]) for k in ['open','high','low','close']};assert all(math.isfinite(x) and x>0 for x in v.values());assert v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high'];assert all(abs(x*4-round(x*4))<1e-7 for x in v.values()),'Off-tick source price';groups.setdefault(local.date().isoformat(),[]).append(dict(minute=local.hour*60+local.minute,utc=utc,**v))
    sessions={};excluded=[]
    for date,rows in groups.items():
        expected=list(range(C['window_start_minute'],C['window_start_minute']+C['window_minutes']))
        if [r['minute'] for r in rows]!=expected or any(b['utc']-a['utc']!=dt.timedelta(minutes=1) for a,b in zip(rows,rows[1:])):excluded.append({'date':date,'rows':len(rows),'reason':'Not exactly all expected consecutive window minutes'});continue
        sessions[date]=rows
    audit={'source_sha256':before,'source_rows':len(raw),'source_dates':len(groups),'eligible_sessions':len(sessions),'eligible_rows':sum(map(len,sessions.values())),'first_date':min(sessions),'last_date':max(sessions),'first_local_minute':'09:30','last_local_minute':'16:14','window_minutes':C['window_minutes'],'excluded_dates':excluded,'boundary':'Fixed exported 09:30–16:15 window; not an inferred exchange session/holiday calendar. No dated contract, roll-adjustment or quality fields supplied.'}
    return sessions,audit

def extent(rows,t,level,horizon):
    future=rows[t+1:t+1+horizon]
    if len(future)!=horizon:return None
    up=max(r['high'] for r in future)-level;down=level-min(r['low'] for r in future)
    return max(0.,min(up,down))

def events(sessions):
    result=[]
    for date,rows in sessions.items():
        low=min(r['low'] for r in rows);high=max(r['high'] for r in rows)
        for shift in [0.]+C['control_shifts_points']:
            for k in range(math.floor((low-shift)/25),math.ceil((high-shift)/25)+1):
                level=25*k+shift;touch=next((i for i,r in enumerate(rows) if r['low']<=level<=r['high']),None)
                if touch is None:continue
                prior=rows[touch-C['prior_range_minutes']:touch] if touch>=C['prior_range_minutes'] else []
                prior_range=max(r['high'] for r in prior)-min(r['low'] for r in prior) if prior else None
                for horizon in C['horizons_minutes']:
                    radius=extent(rows,touch,level,horizon)
                    if radius is None:continue
                    result.append(dict(date=date,shift=shift,k=k,kind=level_class(k),touch=touch,horizon=horizon,prior_range=prior_range,radius=radius))
    return result

def match(real,control):
    options=[]
    for i,a in enumerate(real):
        if a['prior_range'] is None:continue
        for j,b in enumerate(control):
            if b['prior_range'] is None:continue
            if a['date']==b['date'] and a['touch']//C['time_bin_minutes']==b['touch']//C['time_bin_minutes'] and math.floor(a['prior_range']/C['prior_range_bin_points'])==math.floor(b['prior_range']/C['prior_range_bin_points']):
                options.append((abs(a['touch']-b['touch']),abs(a['prior_range']-b['prior_range']),a['k'],b['k'],i,j))
    used_a=set();used_b=set();pairs=[]
    for *_,i,j in sorted(options):
        if i not in used_a and j not in used_b:used_a.add(i);used_b.add(j);pairs.append((real[i],control[j]))
    return pairs

def interval(values,dates,key):
    groups={}
    for x,date in zip(values,dates):groups.setdefault(date,[]).append(x)
    if not groups:return [None,None]
    g=[groups[d] for d in sorted(groups)];sums=np.array([sum(x) for x in g]);counts=np.array([len(x) for x in g]);seed=int.from_bytes(hashlib.sha256((str(C['seed'])+'|'+key).encode()).digest()[:8],'little');ix=np.random.default_rng(seed).integers(len(g),size=(C['bootstrap_repetitions'],len(g)));means=sums[ix].sum(1)/counts[ix].sum(1);return np.quantile(means,[.025,.975]).tolist()

def summary(ev):
    x=[e['radius'] for e in ev];return {'events':len(x),'sessions':len({e['date'] for e in ev}),'median_points':float(np.median(x)) if x else None,'q25_points':float(np.quantile(x,.25)) if x else None,'q75_points':float(np.quantile(x,.75)) if x else None,'mean_points':float(np.mean(x)) if x else None,**{'both_'+str(r):sum(v>=r for v in x) for r in C['radii_points']}}

def aggregate(ev):
    raw=[];paired=[];pair_hashes={}
    for horizon in C['horizons_minutes']:
        for kind in ['all','25-only','50-only','100']:
            real=[e for e in ev if e['shift']==0 and e['horizon']==horizon and (kind=='all' or e['kind']==kind)]
            for shift in [0.]+C['control_shifts_points']:
                selection=[e for e in ev if e['shift']==shift and e['horizon']==horizon and (kind=='all' or e['kind']==kind)]
                raw.append(dict(horizon=horizon,kind=kind,shift=shift,**summary(selection)))
            for shift in C['control_shifts_points']:
                control=[e for e in ev if e['shift']==shift and e['horizon']==horizon and (kind=='all' or e['kind']==kind)];pairs=match(real,control);n=len(pairs);radius=[a['radius']-b['radius'] for a,b in pairs];hit=[100*((a['radius']>=8)-(b['radius']>=8)) for a,b in pairs];dates=[a['date'] for a,b in pairs];key=f'{horizon}|{kind}|{shift}'
                rc=interval(radius,dates,key+'|radius');hc=interval(hit,dates,key+'|hit');paired.append(dict(horizon=horizon,kind=kind,shift=shift,real_events=len(real),control_events=len(control),real_with_prior=sum(e['prior_range'] is not None for e in real),control_with_prior=sum(e['prior_range'] is not None for e in control),pairs=n,paired_sessions=len(set(dates)),real_both8=sum(a['radius']>=8 for a,b in pairs),control_both8=sum(b['radius']>=8 for a,b in pairs),real_median_points=float(np.median([a['radius'] for a,b in pairs])) if n else None,control_median_points=float(np.median([b['radius'] for a,b in pairs])) if n else None,mean_pair_radius_difference=sum(radius)/n if n else None,radius_difference_low=rc[0],radius_difference_high=rc[1],hit_difference_pp=sum(hit)/n if n else None,hit_difference_low_pp=hc[0],hit_difference_high_pp=hc[1],maximum_touch_time_difference=max((abs(a['touch']-b['touch']) for a,b in pairs),default=None),maximum_prior_range_difference=max((abs(a['prior_range']-b['prior_range']) for a,b in pairs),default=None)))
                pair_hashes[key]=hashlib.sha256(json.dumps(pairs,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return raw,paired,pair_hashes

def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)

def main():
    a=argparse.ArgumentParser();a.add_argument('--input',required=True,type=Path);a.add_argument('--output',type=Path,default=P/'results');args=a.parse_args();sessions,audit=load(args.input);ev=events(sessions);raw,paired,hashes=aggregate(ev);args.output.mkdir(parents=True,exist_ok=True);write_csv(args.output/'raw-summary.csv',raw);write_csv(args.output/'matched-summary.csv',paired)
    record={'audit':audit,'event_rows_all_horizons':len(ev),'main_matched':[r for r in paired if r['horizon']==60 and r['shift']==12.5],'event_fingerprint':hashlib.sha256(json.dumps(ev,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'pair_fingerprints':hashes,'interpretation':C['interpretation'],'source_unchanged':hashlib.sha256(args.input.read_bytes()).hexdigest()==C['source_sha256']};assert record['source_unchanged'];(args.output/'summary.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(record['main_matched'],indent=2));print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
