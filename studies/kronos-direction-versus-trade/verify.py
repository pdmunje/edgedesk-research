
from pathlib import Path
from collections import defaultdict,Counter
import argparse,csv,json,hashlib,math
BASE=Path(__file__).resolve().parent

def check(args):
 cfg=json.loads((BASE/'config.json').read_text());fingerprints={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.input,args.reference]};assert fingerprints[str(args.input)]==cfg['input_sha256']
 with args.input.open(encoding='utf-8',newline='') as f:raw=list(csv.DictReader(f))
 groups=defaultdict(list);markets=defaultdict(list);records=[]
 for row in raw:
  if row['phase']!='history' or not cfg['historical_first']<=row['target_date']<=cfg['historical_last']:continue
  prior,pred,op,cl=[float(row[k]) for k in ['previous_close','predicted_close','actual_open','actual_close']];b=(pred>prior)-(pred<prior);a=(cl>prior)-(cl<prior);tick,m=cfg['specs'][row['symbol']];cost=5+2*tick*m if b else 0;gross=round(b*(cl-op)*m,2);net=round(gross-cost,2)
  assert abs(b*(cl-prior)-b*(op-prior)-b*(cl-op))<1e-8
  for k,value in [('bias',b),('cost_usd',cost),('gross_usd',gross),('net_usd',net)]:assert abs(float(row[k])-value)<1e-7
  cor=a!=0 and b==a;cohort='Actual close-to-close flat' if a==0 else 'Correct nonflat direction' if cor else 'Incorrect nonflat direction';outcome='No trade' if b==0 else 'Net win' if net>0 else 'Net loss' if net<0 else 'Entered breakeven';record=(a,b,cor,gross,net,cohort,outcome)
  key=(row['symbol'],row['model'],int(row['lookback']),row['variant']);groups[key].append(record);markets[row['symbol']].append(record);records.append(record)
 def summary(g):
  n=len(g);correct=[x for x in g if x[2]];loss=[x for x in correct if x[4]<0];entered=[x for x in g if x[1]!=0]
  return dict(forecast_rows=n,nonflat_direction_rows=sum(x[0]!=0 for x in g),correct_direction_rows=len(correct),correct_net_losses=len(loss),correct_losses_negative_gross=sum(x[3]<0 for x in loss),correct_losses_zero_gross=sum(x[3]==0 for x in loss),correct_losses_positive_gross=sum(x[3]>0 for x in loss),actual_flat_rows=sum(x[0]==0 for x in g),entered_trades=len(entered),no_trade_rows=n-len(entered),net_wins=sum(x[4]>0 for x in entered),net_losses=sum(x[4]<0 for x in entered),entered_breakeven=sum(x[4]==0 for x in entered),incorrect_net_wins=sum(x[5]=='Incorrect nonflat direction' and x[4]>0 for x in g))
 r=json.loads((BASE/'results.json').read_text());assert len(records)==43098 and r['summary']==summary(records)
 for x in r['markets']:assert {k:v for k,v in x.items() if k!='symbol'}==summary(markets[x['symbol']])
 old=list(csv.DictReader(args.reference.open(encoding='utf-8',newline='')));old={(x['symbol'],x['model'],int(x['lookback']),x['variant']):x for x in old}
 rows=list(csv.DictReader((BASE/'series.csv').open(encoding='utf-8',newline='')));assert len(rows)==len(groups)==len(old)==132
 for x in rows:
  key=(x['symbol'],x['model'],int(x['lookback']),x['variant']);expected=summary(groups[key]);assert all(int(x[k])==v for k,v in expected.items());o=old[key]
  for new,ref in [('forecast_rows','days'),('nonflat_direction_rows','direction_days'),('correct_direction_rows','direction_correct'),('actual_flat_rows','flat_actual_days'),('entered_trades','trades'),('no_trade_rows','no_trade_days'),('net_wins','winners'),('net_losses','losers'),('entered_breakeven','breakeven')]:assert expected[new]==int(o[ref])
 for x in csv.DictReader((BASE/'cohorts.csv').open(encoding='utf-8',newline='')):
  a=[z for z in markets[x['symbol']] if z[5]==x['cohort']];counts=Counter(z[6] for z in a)
  assert (int(x['rows']),int(x['net_wins']),int(x['net_losses']),int(x['entered_breakeven']),int(x['no_trade']))==(len(a),counts['Net win'],counts['Net loss'],counts['Entered breakeven'],counts['No trade'])
 for g in [records,*markets.values(),*groups.values()]:
  z=summary(g);assert z['correct_losses_negative_gross']+z['correct_losses_zero_gross']+z['correct_losses_positive_gross']==z['correct_net_losses'];assert z['net_wins']+z['net_losses']+z['entered_breakeven']+z['no_trade_rows']==len(g)
 # Invented mechanics: long/short can be correct against preceding close and lose after a gap; small gain can lose after costs; flat bias stays out.
 assert round((70.4-70.6)*1000-25,2)==-225
 assert round(-1*(69.6-69.4)*1000-25,2)==-225
 assert .25*50-30==-17.5
 assert 0*(101-100)==0
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in fingerprints.items())
 proof=dict(status='passed',scalar_forecasts=43098,gap_identity_rows=43098,independent_series=132,archived_series_count_checks=132,market_summaries=4,cohort_rows=12,invented_mechanics=4,source_fingerprints_unchanged=2)
 (BASE/'verification.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);check(p.parse_args())
