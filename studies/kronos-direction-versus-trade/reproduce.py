
"""Saved forecasts: close-to-close correctness versus open-to-close simulated trades."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd
BASE=Path(__file__).resolve().parent

def calculate(path):
 cfg=json.loads((BASE/'config.json').read_text());assert hashlib.sha256(path.read_bytes()).hexdigest()==cfg['input_sha256']
 raw=pd.read_csv(path,float_precision='round_trip');h=raw[(raw.phase=='history')&(raw.target_date>=cfg['historical_first'])&(raw.target_date<=cfg['historical_last'])].copy();assert len(h)==43098
 keys=['symbol','model','lookback','variant','target_date'];assert not h.duplicated(keys).any();assert np.isfinite(h[['previous_close','predicted_close','actual_open','actual_close']].to_numpy()).all()
 h['b']=np.sign(h.predicted_close-h.previous_close).astype(int);h['a']=np.sign(h.actual_close-h.previous_close).astype(int);h['correct']=(h.a!=0)&(h.b==h.a)
 h['trade_points']=h.b*(h.actual_close-h.actual_open);h['close_points']=h.b*(h.actual_close-h.previous_close);h['gap_points']=h.b*(h.actual_open-h.previous_close)
 assert np.allclose(h.close_points-h.gap_points,h.trade_points,atol=1e-8,rtol=0)
 m=h.symbol.map({s:v[1] for s,v in cfg['specs'].items()});t=h.symbol.map({s:v[0] for s,v in cfg['specs'].items()});h['cost']=np.where(h.b!=0,5+2*t*m,0);h['gross']=(h.trade_points*m).round(2);h['net']=(h.gross-h.cost).round(2)
 for new,old in [('b','bias'),('cost','cost_usd'),('gross','gross_usd'),('net','net_usd')]:assert np.allclose(h[new],h[old],atol=1e-8,rtol=0)
 h['cohort']=np.where(h.a==0,'Actual close-to-close flat',np.where(h.correct,'Correct nonflat direction','Incorrect nonflat direction'))
 h['outcome']=np.where(h.b==0,'No trade',np.where(h.net>0,'Net win',np.where(h.net<0,'Net loss','Entered breakeven')))
 def summarize(g):
  cor=g[g.correct];loss=cor[cor.net<0];entered=g[g.b!=0]
  return dict(forecast_rows=len(g),nonflat_direction_rows=int((g.a!=0).sum()),correct_direction_rows=len(cor),correct_net_losses=len(loss),correct_losses_negative_gross=int((loss.gross<0).sum()),correct_losses_zero_gross=int((loss.gross==0).sum()),correct_losses_positive_gross=int((loss.gross>0).sum()),actual_flat_rows=int((g.a==0).sum()),entered_trades=len(entered),no_trade_rows=int((g.b==0).sum()),net_wins=int((entered.net>0).sum()),net_losses=int((entered.net<0).sum()),entered_breakeven=int((entered.net==0).sum()),incorrect_net_wins=int(((g.cohort=='Incorrect nonflat direction')&(g.net>0)).sum()))
 markets=[dict(symbol=s,**summarize(g)) for s,g in h.groupby('symbol',sort=True)]
 series=[dict(zip(['symbol','model','lookback','variant'],k))|summarize(g) for k,g in h.groupby(['symbol','model','lookback','variant'],sort=True)]
 cohorts=[]
 for s,g in h.groupby('symbol',sort=True):
  for name in ['Correct nonflat direction','Incorrect nonflat direction','Actual close-to-close flat']:
   x=g[g.cohort==name];counts=x.outcome.value_counts();cohorts.append(dict(symbol=s,cohort=name,rows=len(x),net_wins=int(counts.get('Net win',0)),net_losses=int(counts.get('Net loss',0)),entered_breakeven=int(counts.get('Entered breakeven',0)),no_trade=int(counts.get('No trade',0))))
 result=dict(input_rows=len(raw),historical_rows=len(h),excluded_historical_extension_rows=132,excluded_forward_rows=264,identity_rows=len(h),summary=summarize(h),markets=markets)
 return result,pd.DataFrame(series),pd.DataFrame(cohorts)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);args=p.parse_args();r,s,c=calculate(args.input);(BASE/'results.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');s.to_csv(BASE/'series.csv',index=False);c.to_csv(BASE/'cohorts.csv',index=False);pd.DataFrame(r['markets']).to_csv(BASE/'markets.csv',index=False);print(json.dumps(r,indent=2))
