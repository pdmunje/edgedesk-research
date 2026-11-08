"""Matched-entry exit-policy comparison on authorized saved Buy FVG references."""
import argparse,csv,json,hashlib,math,statistics
from pathlib import Path
from datetime import datetime,timedelta,time
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent;NY=ZoneInfo('America/New_York');TARGETS=[32,64,96];PATHS=['low_first','high_first'];POLICIES=['fixed_stop','entry_stop_after_high16','entry_stop_after_close16']
def load(path):
 expected=json.loads((ROOT/'config.json').read_text())['source_sha256'];assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
 rows=[]
 with Path(path).open(encoding='utf-8-sig',newline='') as f:
  for raw in csv.DictReader(f):
   t=datetime.fromisoformat(raw['time']).astimezone(NY);assert t.second==0 and t.microsecond==0
   px=[]
   for k in ['open','high','low','close']:
    v=float(raw[k]);assert math.isfinite(v) and v>0 and abs(v*4-round(v*4))<1e-8;px.append(round(v*4))
   o,h,l,c=px;assert l<=min(o,c)<=max(o,c)<=h
   try:v=float(raw['Buy FVG']);level=round(v*4) if math.isfinite(v) and v>0 else None
   except ValueError:level=None
   if level is not None:assert abs(v*4-level)<1e-8
   assert not rows or t>rows[-1]['time']
   rows.append(dict(time=t,o=o,h=h,l=l,c=c,level=level))
 for i,r in enumerate(rows):r['ref']=rows[i-1]['level'] if i and (r['time']-rows[i-1]['time']).total_seconds()==60 else None
 return rows

def windows(rows):
 lookup={r['time']:i for i,r in enumerate(rows)};out=[];audit=[]
 for day in sorted({r['time'].date() for r in rows}):
  start=datetime.combine(day,time(8,35),NY);end=datetime.combine(day,time(15,55),NY);i=lookup.get(start);j=lookup.get(end);reason='eligible'
  if i is None or j is None:reason='missing_boundary'
  elif j-i!=440 or any((rows[n+1]['time']-rows[n]['time']).total_seconds()!=60 for n in range(i,j)):reason='missing_minute'
  audit.append(dict(date=str(day),status=reason))
  if reason=='eligible':out.append((str(day),i,j))
 return out,audit

def vertices(r,path):return [r['o'],r['l'],r['h'],r['c']] if path=='low_first' else [r['o'],r['h'],r['l'],r['c']]
def fill_exit(t,price,reason,moved):return dict(exit_bar=t,exit_ticks=price,reason=reason,moved=moved)
def holding_bar(rows,t,e,target,path,policy,state,first=False):
 r=rows[t];E=e['entry_ticks'];S=E if state['moved'] else e['initial_stop_ticks'];T=E+target
 if not first:
  if state['arm_next']:state['moved']=True;S=E;state['arm_next']=False
  if r['o']<=S:return fill_exit(t,r['o'],('entry_stop' if state['moved'] else 'fixed_stop')+('_gap' if r['o']<S else ''),state['moved'])
  if r['o']>=T:return fill_exit(t,T,'target',state['moved'])
 if t==e['cutoff_bar']:return fill_exit(t,r['o'],'window_close',state['moved'])
 vv=vertices(r,path);phase=e['entry_phase'] if first else -1
 points=([E]+vv[phase+1:]) if first and phase>=0 else vv
 max_seen=points[0]
 for a,b in zip(points,points[1:]):
  if b>=a and a<=T<=b:return fill_exit(t,T,'target',state['moved'])
  if b<a and b<=S<=a:return fill_exit(t,S,'entry_stop' if state['moved'] else 'fixed_stop',state['moved'])
  max_seen=max(max_seen,b)
 if policy!='fixed_stop' and not state['moved']:
  qualify=max_seen>=E+16 if policy=='entry_stop_after_high16' else r['c']>=E+16
  if qualify:state['arm_next']=True
 return None

def baseline(rows,i,j,target,path):
 events=[];position=None;pending=None;streak=0;state=None
 for t in range(i,j+1):
  if position:
   result=holding_bar(rows,t,position,target,path,'fixed_stop',state)
   if result:events.append(dict(position,**result));position=None
  if t==j:break
  if position is None and pending is not None:
   trigger=pending;pending=None;r=rows[t];phase=-1
   if r['o']>=trigger:entry=r['o']
   elif r['h']>=trigger:entry=trigger;phase=1 if path=='low_first' else 0
   else:entry=None
   if entry is not None:
    position=dict(entry_bar=t,entry_phase=phase,entry_ticks=entry,trigger_ticks=trigger,initial_stop_ticks=trigger-32,cutoff_bar=j)
    state={'moved':False,'arm_next':False};result=holding_bar(rows,t,position,target,path,'fixed_stop',state,True)
    if result:events.append(dict(position,**result));position=None
  r=rows[t];streak=streak+1 if r['ref'] is not None and r['c']<r['ref'] else 0
  if position is None and streak>=5 and t<j-1:pending=r['ref']
 return events

def replay(rows,e,target,path,policy):
 state={'moved':False,'arm_next':False}
 for t in range(e['entry_bar'],e['cutoff_bar']+1):
  result=holding_bar(rows,t,e,target,path,policy,state,t==e['entry_bar'])
  if result:return dict(e,**result)
 raise AssertionError('Unclosed replay')
def profit(e):return e['exit_ticks']-e['entry_ticks']
def digest(events):return hashlib.sha256(json.dumps(events,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def stats(events):
 g=[profit(e) for e in events];n=len(g);net=[v-3 for v in g];mean=lambda x:statistics.mean(x) if x else None
 return dict(trades=n,gross_mean_ticks=mean(g),net_1_mean_ticks=None if not n else mean(g)-1,net_3_mean_ticks=mean(net),net_5_mean_ticks=None if not n else mean(g)-5,gross_median_ticks=statistics.median(g) if n else None,gross_total_ticks=sum(g),net_3_total_ticks=sum(net),gross_zero_trades=sum(x==0 for x in g),gross_wins=sum(x>0 for x in g),gross_losses=sum(x<0 for x in g),net_3_wins=sum(x>0 for x in net),net_3_losses=sum(x<0 for x in net),net_3_flat=sum(x==0 for x in net),stop_raised_trades=sum(e['moved'] for e in events),entry_stop_exits=sum(e['reason'].startswith('entry_stop') for e in events),entry_stop_gap_exits=sum(e['reason']=='entry_stop_gap' for e in events),target_exits=sum(e['reason']=='target' for e in events),fixed_stop_exits=sum(e['reason'].startswith('fixed_stop') for e in events),window_close_exits=sum(e['reason']=='window_close' for e in events),worst_gross_trade_ticks=min(g) if n else None,event_hash=digest(events))
def run(rows):
 ww,eligibility=windows(rows);summary=[];paired=[];sessions=[]
 for path in PATHS:
  for target in TARGETS:
   base=[]
   for date,i,j in ww:base+=baseline(rows,i,j,target,path)
   for policy in POLICIES:
    ee=[replay(rows,e,target,path,policy) for e in base]
    if policy=='fixed_stop':assert ee==base
    assert all(a['entry_bar']==b['entry_bar'] and a['entry_ticks']==b['entry_ticks'] for a,b in zip(base,ee))
    summary.append(dict(path=path,target_ticks=target,policy=policy,eligible_windows=len(ww),**stats(ee)))
    for date,i,j in ww:
     ss=[e for e in ee if i<=e['entry_bar']<j];sessions.append(dict(path=path,target_ticks=target,policy=policy,date=date,trades=len(ss),net_3_total_ticks=sum(profit(e)-3 for e in ss)))
    if policy!='fixed_stop':
     changes=[profit(b)-profit(a) for a,b in zip(base,ee)]
     paired.append(dict(path=path,target_ticks=target,policy=policy,matched_entries=len(base),mean_change_ticks=statistics.mean(changes) if changes else None,total_change_ticks=sum(changes),improved=sum(x>0 for x in changes),worse=sum(x<0 for x in changes),unchanged=sum(x==0 for x in changes),baseline_target_to_entry_stop=sum(a['reason']=='target' and b['reason'].startswith('entry_stop') for a,b in zip(base,ee)),baseline_loss_to_exact_zero=sum(profit(a)<0 and profit(b)==0 for a,b in zip(base,ee))))
 return summary,paired,sessions,eligibility

def write(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();rows=load(a.input);summary,paired,sessions,elig=run(rows);out=ROOT/'results';out.mkdir(exist_ok=True)
 for name,rr in [('summary.csv',summary),('paired-comparison.csv',paired),('sessions.csv',sessions),('eligibility.csv',elig)]:write(out/name,rr)
 audit=dict(source_rows=len(rows),first=rows[0]['time'].isoformat(),last=rows[-1]['time'].isoformat(),source_sha256=hashlib.sha256(Path(a.input).read_bytes()).hexdigest(),missing_source_FVG=sum(r['level'] is None for r in rows),unavailable_lagged_FVG=sum(r['ref'] is None for r in rows),eligible_dates=[x['date'] for x in elig if x['status']=='eligible'],excluded_candidates=[x for x in elig if x['status']!='eligible'],scope='Historical saved-reference reconstruction, not old-code replication or live-availability validation; management variants reuse each fixed-stop target/path entry ledger. Two chosen intrabar paths, not rigorous performance bounds.')
 (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2));print('summary',len(summary),'paired',len(paired),'sessions',len(sessions))
if __name__=='__main__':main()
