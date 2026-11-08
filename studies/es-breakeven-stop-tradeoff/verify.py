"""Independent candidate-order/event reconstruction and fixed-entry replay checks."""
import argparse,csv,json,math,statistics
from pathlib import Path
from datetime import timedelta
import reproduce as r
ROOT=Path(__file__).resolve().parent

def order_candidates(rows,i,j):
 orders={}
 for t in range(i+4,j-1):
  last=rows[t-4:t+1]
  if all(x['ref'] is not None and x['c']<x['ref'] for x in last):orders[t+1]=rows[t]['ref']
 return orders

def exit_event(rows,e,target,path,policy):
 E=e['entry_ticks'];T=E+target;raised=False;raise_at=None
 for t in range(e['entry_bar'],e['cutoff_bar']+1):
  if raise_at==t:raised=True
  S=E if raised else e['initial_stop_ticks'];x=rows[t];first=t==e['entry_bar']
  def result(px,why):return dict(e,exit_bar=t,exit_ticks=px,reason=why,moved=raised)
  if not first:
   if x['o']<=S:return result(x['o'],('entry_stop' if raised else 'fixed_stop')+('_gap' if x['o']<S else ''))
   if x['o']>=T:return result(T,'target')
  if t==e['cutoff_bar']:return result(x['o'],'window_close')
  if first and e['entry_phase']>=0:
   # A buy stop enters on the rise to the bar high. A low-first low precedes entry.
   if x['h']>=T:return result(T,'target')
   stop_hit=(x['l']<=S if path=='high_first' else x['c']<=S)
   if stop_hit:return result(S,'entry_stop' if raised else 'fixed_stop')
  else:
   stop_hit=x['l']<=S;target_hit=x['h']>=T
   if stop_hit and (not target_hit or path=='low_first'):return result(S,'entry_stop' if raised else 'fixed_stop')
   if target_hit:return result(T,'target')
  if not raised and policy!='fixed_stop':
   hit=x['h']>=E+16 if policy=='entry_stop_after_high16' else x['c']>=E+16
   if hit and raise_at is None:raise_at=t+1
 raise AssertionError('Missing exit')

def independent_base(rows,i,j,target,path):
 orders=order_candidates(rows,i,j);out=[];cursor=i
 for t,trigger in orders.items():
  if t<cursor or rows[t]['h']<trigger:continue
  x=rows[t];E=max(x['o'],trigger);phase=-1 if x['o']>=trigger else (1 if path=='low_first' else 0)
  e=dict(entry_bar=t,entry_phase=phase,entry_ticks=E,trigger_ticks=trigger,initial_stop_ticks=trigger-32,cutoff_bar=j)
  e=exit_event(rows,e,target,path,'fixed_stop');out.append(e);cursor=e['exit_bar']+1
 return out

def synthetic():
 cases=[]
 def rows(v):return [dict(zip(['o','h','l','c'],x)) for x in v]
 def entry(phase=-1):return dict(entry_bar=0,entry_phase=phase,entry_ticks=1000,trigger_ticks=1000,initial_stop_ticks=968,cutoff_bar=2)
 def check(v,policy,px,bar,reason,path='low_first',phase=-1,target=32):
  rr=rows(v);e=entry(phase);a=r.replay(rr,e,target,path,policy);b=exit_event(rr,e,target,path,policy);assert a==b;assert (a['exit_ticks'],a['exit_bar'],a['reason'])==(px,bar,reason),(a,px,bar,reason)
 base=[[1000,1020,990,1018],[1004,1010,999,1008],[1010,1020,1000,1015]]
 check(base,'entry_stop_after_high16',1000,1,'entry_stop');cases.append('completed-bar activation begins next bar')
 check(base,'entry_stop_after_high16',1000,1,'entry_stop',path='high_first');cases.append('same-bar reversal cannot use a newly raised stop')
 check([[1000,1020,990,1018],[995,1010,990,1008],[1010,1020,1000,1015]],'entry_stop_after_high16',995,1,'entry_stop_gap');cases.append('adverse gap below entry is not flat')
 check([[1000,1020,990,1018],[1000,1010,990,1008],[1010,1020,1000,1015]],'entry_stop_after_high16',1000,1,'entry_stop');cases.append('opening equality is a touch, not adverse-gap loss')
 wick=[[1000,1020,990,1004],[1004,1010,999,1008],[1010,1020,1000,1015]]
 check(wick,'entry_stop_after_high16',1000,1,'entry_stop');check(wick,'entry_stop_after_close16',1010,2,'window_close');cases.append('high trigger and close trigger differ')
 check([[990,1020,960,1018],[1004,1010,1001,1008],[1010,1020,1000,1015]],'fixed_stop',1010,2,'window_close',phase=1);cases.append('pre-entry low excluded under low-first path')
 check([[990,1020,960,1018],[1004,1010,1001,1008],[1010,1020,1000,1015]],'fixed_stop',968,0,'fixed_stop',path='high_first',phase=0);cases.append('post-entry low included under high-first path')
 both=[[1000,1040,960,1008],[1004,1010,999,1008],[1010,1020,1000,1015]]
 check(both,'fixed_stop',968,0,'fixed_stop');check(both,'fixed_stop',1032,0,'target',path='high_first');cases.append('two explicit paths disagree on a both-hit bar')
 check([[1000,1008,990,1004],[960,970,950,965],[1010,1020,1000,1015]],'fixed_stop',960,1,'fixed_stop_gap');cases.append('initial stop also gaps at observed open')
 check([[1000,1016,990,1016],[1004,1010,999,1008],[1010,1020,1000,1015]],'entry_stop_after_close16',1000,1,'entry_stop');cases.append('trigger equality qualifies')
 check([[1000,1010,990,1008],[1008,1012,1001,1008],[1009,2000,900,1900]],'fixed_stop',1009,2,'window_close');cases.append('cutoff open excludes later cutoff-bar extremes')
 check([[1000,1040,990,1018],[1004,1010,999,1008],[1010,1020,1000,1015]],'entry_stop_after_high16',1032,0,'target');cases.append('target exit precedes any future stop activation')
 rr=rows([[1000,1010,990,1000]]*5+[[1000,1030,999,1025],[1040,1045,1035,1040]])
 for x in rr:x['ref']=1020
 a=r.baseline(rr,0,6,32,'low_first');b=independent_base(rr,0,6,32,'low_first');assert a==b and len(a)==1 and a[0]['entry_bar']==5;cases.append('five completed closes arm only next-bar entry')
 rr[0]['c']=1040;rr[0]['h']=1040;a=r.baseline(rr,0,6,32,'low_first');assert not a;cases.append('no fresh entry at cutoff open')
 assert (1000-1000)-3==-3 and (995-1000)-3==-8;cases.append('price-flat and gap exits lose after costs')
 return cases

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();cases=synthetic();rows=r.load(a.input);ww,elig=r.windows(rows);checks=hashes=0;actual={};summary=list(csv.DictReader((ROOT/'results/summary.csv').open()))
 for date,i,j in ww:
  assert all(rows[i+n]['time']==rows[i]['time']+timedelta(minutes=n) for n in range(441));checks+=1
 for path in r.PATHS:
  for target in r.TARGETS:
   base=[]
   for date,i,j in ww:base+=independent_base(rows,i,j,target,path)
   for policy in r.POLICIES:
    ee=[exit_event(rows,e,target,path,policy) for e in base];actual[(path,target,policy)]=ee
    saved=next(x for x in summary if x['path']==path and int(x['target_ticks'])==target and x['policy']==policy)
    assert r.digest(ee)==saved['event_hash'],(path,target,policy);hashes+=1
    g=[e['exit_ticks']-e['entry_ticks'] for e in ee];n=len(g);net=[x-3 for x in g]
    vals={'trades':n,'eligible_windows':len(ww),'gross_total_ticks':sum(g),'net_3_total_ticks':sum(net),'gross_zero_trades':g.count(0),'gross_wins':sum(x>0 for x in g),'gross_losses':sum(x<0 for x in g),'net_3_wins':sum(x>0 for x in net),'net_3_losses':sum(x<0 for x in net),'net_3_flat':net.count(0),'stop_raised_trades':sum(e['moved'] for e in ee),'entry_stop_exits':sum(e['reason'].startswith('entry_stop') for e in ee),'entry_stop_gap_exits':sum(e['reason']=='entry_stop_gap' for e in ee),'target_exits':sum(e['reason']=='target' for e in ee),'fixed_stop_exits':sum(e['reason'].startswith('fixed_stop') for e in ee),'window_close_exits':sum(e['reason']=='window_close' for e in ee),'worst_gross_trade_ticks':min(g) if n else None,'gross_mean_ticks':sum(g)/n if n else None,'net_1_mean_ticks':sum(g)/n-1 if n else None,'net_3_mean_ticks':sum(net)/n if n else None,'net_5_mean_ticks':sum(g)/n-5 if n else None,'gross_median_ticks':statistics.median(g) if n else None}
    for key,v in vals.items():
     assert saved[key]=='' if v is None else math.isclose(float(saved[key]),v,abs_tol=1e-10,rel_tol=1e-10),(key,saved[key],v)
     checks+=1
 for saved in csv.DictReader((ROOT/'results/paired-comparison.csv').open()):
  path,target,policy=saved['path'],int(saved['target_ticks']),saved['policy'];base=actual[path,target,'fixed_stop'];ee=actual[path,target,policy];delta=[(b['exit_ticks']-b['entry_ticks'])-(a['exit_ticks']-a['entry_ticks']) for a,b in zip(base,ee)]
  vals={'matched_entries':len(base),'mean_change_ticks':sum(delta)/len(delta),'total_change_ticks':sum(delta),'improved':sum(x>0 for x in delta),'worse':sum(x<0 for x in delta),'unchanged':delta.count(0),'baseline_target_to_entry_stop':sum(a['reason']=='target' and b['reason'].startswith('entry_stop') for a,b in zip(base,ee)),'baseline_loss_to_exact_zero':sum(a['exit_ticks']<a['entry_ticks'] and b['exit_ticks']==b['entry_ticks'] for a,b in zip(base,ee))}
  for key,v in vals.items():assert math.isclose(float(saved[key]),v,abs_tol=1e-10,rel_tol=1e-10);checks+=1
 for saved in csv.DictReader((ROOT/'results/sessions.csv').open()):
  ee=[e for e in actual[saved['path'],int(saved['target_ticks']),saved['policy']] if str(rows[e['entry_bar']]['time'].date())==saved['date']]
  assert len(ee)==int(saved['trades']) and sum(e['exit_ticks']-e['entry_ticks']-3 for e in ee)==int(saved['net_3_total_ticks']);checks+=2
 result={'status':'passed','synthetic_case_groups':len(cases),'cases':cases,'independent_numeric_checks':checks,'full_event_fingerprints':hashes,'matched_variants':12,'eligible_windows':len(ww),'method':'Independent five-bar candidate order scan, first-exit range/event logic and separate summary/session arithmetic; source loader/window selection shared. Two specified intrabar paths are scenarios, not rigorous bounds or real execution.'}
 (ROOT/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
