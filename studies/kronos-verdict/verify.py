
"""Scalar arithmetic and frozen-archive verification. No inference."""
from pathlib import Path
import argparse,csv,json,math,statistics,hashlib
from collections import defaultdict
from datetime import datetime
import numpy as np
BASE=Path(__file__).resolve().parent

def check(args):
 frozen=[args.input,args.archive/'history_by_seed.csv',args.archive/'settings.csv',args.archive/'uncertainty.csv',args.archive/'checks.json',args.archive.parents[1]/'PROJECT_CLOSED.json'];fingerprints={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
 cfg=json.loads((BASE/'config.json').read_text());assert hashlib.sha256(args.input.read_bytes()).hexdigest()==cfg['input_sha256'];assert hashlib.sha256(args.timing.read_bytes()).hexdigest()==cfg['timing_sha256']
 with args.input.open(encoding='utf-8',newline='') as f:raw=list(csv.DictReader(f))
 groups=defaultdict(list);votes=defaultdict(list);actuals={};forwardkeys=set();forwardgroups=defaultdict(list)
 for row in raw:
  symbol=row['symbol'];tick,mult=cfg['specs'][symbol];v={k:float(row[k]) for k in ['previous_close','actual_open','actual_high','actual_low','actual_close','predicted_open','predicted_high','predicted_low','predicted_close']};delta=v['predicted_close']-v['previous_close'];bias=(delta>0)-(delta<0);move=v['actual_close']-v['previous_close'];direction=(move>0)-(move<0);cost=5+2*tick*mult if bias else 0;gross=round(bias*(v['actual_close']-v['actual_open'])*mult,2);net=round(gross-cost,2);long=round((v['actual_close']-v['actual_open'])*mult-5-2*tick*mult,2);short=round((v['actual_open']-v['actual_close'])*mult-5-2*tick*mult,2)
  for k,x in [('bias',bias),('cost_usd',cost),('gross_usd',gross),('net_usd',net),('always_long_net_usd',long),('always_short_net_usd',short)]:assert abs(float(row[k])-x)<1e-7,k
  item=dict(date=row['target_date'],net=net,long=long,short=short,cost=cost,error=abs(v['predicted_close']-v['actual_close']),baseerror=abs(v['previous_close']-v['actual_close']),correct=bias==direction,directional=direction!=0,trade=bias!=0,invalid=v['predicted_high']<max(v['predicted_open'],v['predicted_low'],v['predicted_close']) or v['predicted_low']>min(v['predicted_open'],v['predicted_high'],v['predicted_close']))
  key=(row['variant'],symbol,row['model'],int(row['lookback']))
  if row['phase']=='history' and cfg['historical_first']<=row['target_date']<=cfg['historical_last']:
   groups[key].append(item);votes[(symbol,row['model'],int(row['lookback']),item['date'])].append(bias)
   pricekey=(symbol,item['date']);a=tuple(v[k] for k in ['previous_close','actual_open','actual_high','actual_low','actual_close']);assert pricekey not in actuals or actuals[pricekey]==a;actuals[pricekey]=a
  if row['phase']=='forward':forwardkeys.add(key+(item['date'],));forwardgroups[key].append(item)
 def close(a,b):assert abs(a-b)<1e-7,(a,b)
 def verify_series(filename,data):
  rows=list(csv.DictReader((BASE/filename).open(encoding='utf-8',newline='')));assert len(rows)==132==len(data)
  for row in rows:
   k=(row['variant'],row['symbol'],row['model'],int(row['lookback']));g=sorted(data[k],key=lambda x:x['date']);n=len(g);net=[x['net'] for x in g];eq=peak=dd=0
   for x in net:eq+=x;peak=max(peak,eq);dd=max(dd,peak-eq)
   checks=dict(days=n,trades=sum(x['trade'] for x in g),correct=sum(x['correct'] for x in g if x['directional']),direction_days=sum(x['directional'] for x in g),net_usd=math.fsum(net),always_long_usd=math.fsum(x['long'] for x in g),always_short_usd=math.fsum(x['short'] for x in g),net_without_best5_usd=math.fsum(sorted(net)[:-5]),net_double_cost_usd=math.fsum(x['net']-x['cost'] for x in g),mean_error_points=statistics.mean(x['error'] for x in g),baseline_error_points=statistics.mean(x['baseerror'] for x in g),invalid_candles=sum(x['invalid'] for x in g),max_closed_drawdown_usd=dd,net_2025_usd=math.fsum(x['net'] for x in g if x['date']<'2026-01-01'),net_2026_usd=math.fsum(x['net'] for x in g if x['date']>='2026-01-01'))
   # With two forward days, removing five best days removes both (same declared arithmetic).
   for field,value in checks.items():close(float(row[field]),value)
   close(float(row['error_reduction_percent']),100*(1-checks['mean_error_points']/checks['baseline_error_points']))
   assert row['first_date']==g[0]['date'] and row['last_date']==g[-1]['date']
  return rows
 seeds=verify_series('seeds.csv',groups);verify_series('forward.csv',forwardgroups)
 result=json.loads((BASE/'results.json').read_text());assert result['history_rows']==sum(len(x) for x in groups.values())==43098;assert result['invalid_candles']==sum(x['invalid'] for g in groups.values() for x in g)==8109;assert result['worse_price_series']==sum(float(x['error_reduction_percent'])<0 for x in seeds)==132
 assert len(votes)==result['matched_groups']==14366 and all(len(x)==3 for x in votes.values());assert sum(len(set(x))==1 for x in votes.values())==result['unanimous_groups']==8647
 for q in result['market_quality']:
  a=[x for x in seeds if x['symbol']==q['symbol']];g=[x for k,part in groups.items() if k[1]==q['symbol'] for x in part]
  assert (q['series'],q['worse_series'],q['forecast_rows'],q['invalid_candles'])==(len(a),sum(float(x['error_reduction_percent'])<0 for x in a),len(g),sum(x['invalid'] for x in g))
 for x in csv.DictReader((BASE/'agreement.csv').open(encoding='utf-8',newline='')):
  a=[v for k,v in votes.items() if k[:3]==(x['symbol'],x['model'],int(x['lookback']))]
  assert int(x['matched_days'])==len(a) and int(x['unanimous'])==sum(len(set(v))==1 for v in a)
 t=json.loads(args.timing.read_text());tk={(x['variant'],x['symbol'],x['model'],x['lookback'],x['target_date']) for x in t};assert tk==forwardkeys and len(tk)==264;assert all(datetime.fromisoformat(x['created_at_utc'].replace('Z','+00:00'))<datetime.fromisoformat(x['target_open_utc'].replace('Z','+00:00')) for x in t)
 # Cross-check exact frozen October22 summaries, not a new model run.
 reference=list(csv.DictReader((args.archive/'history_by_seed.csv').open(encoding='utf-8',newline='')));ref={(x['variant'],x['symbol'],x['model'],int(x['lookback'])):x for x in reference};assert len(ref)==132
 for x in seeds:
  old=ref[(x['variant'],x['symbol'],x['model'],int(x['lookback']))]
  for new,oldkey in [('net_usd','net_usd'),('correct','direction_correct'),('days','days'),('invalid_candles','invalid_predicted_candles'),('mean_error_points','mean_close_error_points')]:close(float(x[new]),float(old[oldkey]))
 oldsettings=list(csv.DictReader((args.archive/'settings.csv').open(encoding='utf-8',newline='')));now=list(csv.DictReader((BASE/'settings.csv').open(encoding='utf-8',newline='')));assert len(now)==len(oldsettings)==44
 for a,b in zip(now,oldsettings):
  assert (a['symbol'],a['model'],a['lookback'])==(b['symbol'],b['model'],b['lookback'])
  for k in ['days_per_seed','mean_net_usd','min_net_usd','max_net_usd','positive_seeds','beats_long_seeds','beats_short_seeds','mean_net_without_best5_usd']:close(float(a[k]),float(b[k]))
 ui=list(csv.DictReader((BASE/'uncertainty.csv').open(encoding='utf-8',newline='')));oldi=list(csv.DictReader((args.archive/'uncertainty.csv').open(encoding='utf-8',newline='')));assert len(ui)==len(oldi)==12
 for a,b in zip(ui,oldi):
  for k in ['mean_daily_advantage_usd','lower95_usd','upper95_usd']:close(float(a[k]),float(b[k]))
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in fingerprints.items())
 # Invented examples: correct close-to-close sign can lose an open-to-close trade; zero means no fee; seed average is arithmetic.
 assert round((70.40-70.60)*1000-25,2)==-225;assert (0 if 0==0 else 30)==0;assert statistics.mean([30,-10,10])==10
 proof=dict(status='passed',raw_rows_scalar_checked=len(raw),historical_series_independently_checked=132,forward_series_independently_checked=132,historical_groups=14366,archive_seed_comparisons=132,archive_settings=44,archive_interval_rows=12,before_open_timings=264,invented_mechanics=3,checked_source_files_unchanged=len(fingerprints))
 (BASE/'verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--timing',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);check(p.parse_args())
