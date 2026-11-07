"""Invented fill-price arithmetic only. Does not simulate markets or order queues."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def calculate(config):
 cost=config['tick_points']*config['total_round_trip_cost_ticks'];out=[]
 for case in config['examples']:
  r={'case':case['case'],'data_kind':'invented'}
  for arm in ['limit','confirmation']:
   entry,exit=case[arm+'_entry'],case[arm+'_exit']
   assert (entry is None)==(exit is None),'Entry/exit pair required'
   filled=entry is not None
   r[arm+'_filled']=int(filled)
   r[arm+'_gross_points']=exit-entry if filled else 0
   r[arm+'_cost_points']=cost if filled else 0
   r[arm+'_net_points']=r[arm+'_gross_points']-r[arm+'_cost_points']
  r['paired_confirmation_minus_limit_points']=r['confirmation_net_points']-r['limit_net_points']
  out.append(r)
 return out

def metrics(rows):
 out={}
 for arm in ['limit','confirmation']:
  n=sum(r[arm+'_filled'] for r in rows);total=sum(r[arm+'_net_points'] for r in rows)
  out[arm]={'invented_opportunities':len(rows),'stipulated_fills':n,'net_total_points':total,'net_points_per_invented_opportunity':total/len(rows) if rows else None,'net_points_per_stipulated_fill':total/n if n else None}
 return out

def main():
 config=json.loads((ROOT/'examples.json').read_text());rows=calculate(config);out=ROOT/'results';out.mkdir(exist_ok=True)
 with (out/'illustrations.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 (out/'illustrative-denominators.json').write_text(json.dumps({'warning':'Only these four invented cases, equally weighted to demonstrate denominators. Not market estimates, forecasts, probabilities or evidence for either entry rule.','arithmetic':metrics(rows)},indent=2)+'\n')
 print('Four invented case calculations saved. Zero market observations tested.')
if __name__=='__main__':main()
