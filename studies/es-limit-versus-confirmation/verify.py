"""Verify hand-specified case arithmetic with exact Decimal arithmetic."""
import csv,json
from decimal import Decimal
from pathlib import Path
import reproduce
ROOT=Path(__file__).resolve().parent

def main():
 expected=[('Fast rebound','3.25','1.25','-2.00'),('Continued decline','-5.25','0','5.25'),('Rebound then failure','-4.75','-6.25','-1.50'),('Touch without passive fill','0','2.25','2.25')]
 rows=list(csv.DictReader((ROOT/'results/illustrations.csv').open()));config=json.loads((ROOT/'examples.json').read_text());checks=0
 assert len(rows)==len(expected)==len(config['examples'])==4
 for row,case,exp in zip(rows,config['examples'],expected):
  assert row['case']==exp[0] and row['data_kind']=='invented'
  for arm,col in [('limit',1),('confirmation',2)]:
   entry,exit=case[arm+'_entry'],case[arm+'_exit'];filled=entry is not None
   gross=Decimal(str(exit))-Decimal(str(entry)) if filled else Decimal(0)
   cost=Decimal('0.75') if filled else Decimal(0)
   for key,value in [(arm+'_filled',int(filled)),(arm+'_gross_points',gross),(arm+'_cost_points',cost),(arm+'_net_points',Decimal(exp[col]))]:
    assert Decimal(row[key])==Decimal(str(value)),(key,row[key],value);checks+=1
  assert Decimal(row['paired_confirmation_minus_limit_points'])==Decimal(exp[3]);checks+=1
 generated=reproduce.calculate(config);assert len(generated)==4
 # Cost charged only on an actual stipulated fill, even when gross is exactly flat.
 flat={'tick_points':.25,'total_round_trip_cost_ticks':3,'examples':[{'case':'flat','limit_entry':100,'limit_exit':100,'confirmation_entry':None,'confirmation_exit':None}]}
 f=reproduce.calculate(flat)[0];assert f['limit_net_points']==-.75 and f['confirmation_net_points']==0;checks+=2
 empty=reproduce.metrics([]);assert empty['limit']['net_points_per_stipulated_fill'] is None;checks+=1
 one=reproduce.metrics(reproduce.calculate(flat));assert one['confirmation']['net_points_per_stipulated_fill'] is None and one['confirmation']['net_points_per_invented_opportunity']==0;checks+=2
 saved=json.loads((ROOT/'results/illustrative-denominators.json').read_text())['arithmetic']
 for arm,total in [('limit',Decimal('-6.75')),('confirmation',Decimal('-2.75'))]:
  assert saved[arm]['invented_opportunities']==4 and saved[arm]['stipulated_fills']==3;checks+=2
  assert Decimal(str(saved[arm]['net_total_points']))==total;checks+=1
  assert Decimal(str(saved[arm]['net_points_per_invented_opportunity']))==total/4;checks+=1
  assert abs(Decimal(str(saved[arm]['net_points_per_stipulated_fill']))-total/3)<Decimal('1e-14');checks+=1
 # Zero approach path is undefined, not an invented high-confidence bucket.
 def efficiency(c):
  den=sum(abs(b-a) for a,b in zip(c,c[1:]));return abs(c[-1]-c[0])/den if den else None
 assert efficiency([10,9,8,7,6,5])==1 and efficiency([10,10,10,10,10,10]) is None;checks+=2
 result={'status':'passed','invented_cases':4,'actual_market_observations':0,'arithmetic_and_boundary_checks':checks,'method':'Exact Decimal case calculations, hand-specified net/paired outcomes, zero-fill/flat/empty denominators and approach-path boundaries. Not verification of a market backtest or execution engine.'}
 (ROOT/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
