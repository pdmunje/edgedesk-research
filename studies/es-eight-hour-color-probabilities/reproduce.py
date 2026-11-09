"""Focused descriptive recheck of saved eight-hour ES candle colors. No trades."""
import argparse,csv,hashlib,json,math,statistics
from collections import Counter
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config.json').read_text())
NY=ZoneInfo(CONFIG['timezone'])
LABELS={'all':'All valid transitions','current_red':'Current candle red','current_green':'Current candle green','three_red':'Three red candles','three_green':'Three green candles','five_lower_lows':'Five successive lower lows','five_higher_highs':'Five successive higher highs','cross_above_sma20':'Close crosses above SMA(20)','cross_below_sma20':'Close crosses below SMA(20)'}
def load(path):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CONFIG['input_sha256']:raise ValueError('Authorized file fingerprint differs')
    rows=[]
    for x in csv.DictReader(raw.decode('utf-8-sig').splitlines()):
        t=datetime.fromisoformat(x['time'])
        if t.tzinfo is None:raise ValueError('Timestamp needs offset')
        local=t.astimezone(NY)
        if local.utcoffset()!=t.utcoffset() or local.minute or local.second or local.hour not in [18,2,10]:raise ValueError('Unexpected slot/offset')
        vals={k:float(x[k]) for k in ['open','high','low','close']}
        if not all(math.isfinite(v) and v>0 for v in vals.values()):raise ValueError('Invalid price')
        if not vals['low']<=min(vals['open'],vals['close'])<=max(vals['open'],vals['close'])<=vals['high']:raise ValueError('Invalid OHLC')
        if rows and t<=rows[-1]['time']:raise ValueError('Unordered/duplicate timestamp')
        slot={18:1,2:2,10:3}[local.hour]
        rows.append({**vals,'time':t,'slot':slot,'date':local.date()+timedelta(days=slot==1)})
    return rows

def transition(a,b):
    return (a['slot']==1 and b['slot']==2 and a['date']==b['date']) or (a['slot']==2 and b['slot']==3 and a['date']==b['date']) or (a['slot']==3 and b['slot']==1)

def condition(rows,i,name):
    if name=='all':return True
    if name=='current_red':return rows[i]['close']<rows[i]['open']
    if name=='current_green':return rows[i]['close']>rows[i]['open']
    if name in ['three_red','three_green']:
        if i<2:return None
        return all((x['close']<x['open'] if name=='three_red' else x['close']>x['open']) for x in rows[i-2:i+1])
    if name in ['five_lower_lows','five_higher_highs']:
        if i<5:return None
        key='low' if name=='five_lower_lows' else 'high'
        return all((rows[j][key]<rows[j-1][key] if key=='low' else rows[j][key]>rows[j-1][key]) for j in range(i-4,i+1))
    if name in ['cross_above_sma20','cross_below_sma20']:
        if i<20:return None
        now=sum(x['close'] for x in rows[i-19:i+1])/20
        prev=sum(x['close'] for x in rows[i-20:i])/20
        return rows[i]['close']>now and rows[i-1]['close']<=prev if name=='cross_above_sma20' else rows[i]['close']<now and rows[i-1]['close']>=prev
    raise ValueError(name)

def summarize(rows):
    events=[];invalid=0;dojis=0
    for i,(a,b) in enumerate(zip(rows,rows[1:])):
        if not transition(a,b):invalid+=1;continue
        if b['close']==b['open']:dojis+=1;continue
        events.append((i,a,b))
    output=[]
    for year in CONFIG['period_start_years']:
        for target in [1,2,3]:
            pool=[(i,a,b) for i,a,b in events if a['time'].year>=year and b['slot']==target]
            for name in ['all',*CONFIG['conditions']]:
                eligible=[(i,a,b) for i,a,b in pool if condition(rows,i,name) is not None]
                chosen=[(i,a,b) for i,a,b in eligible if condition(rows,i,name)]
                n=len(chosen);green=sum(b['close']>b['open'] for _,_,b in chosen)
                base_n=len(eligible);base_green=sum(b['close']>b['open'] for _,_,b in eligible)
                body=[b['close']-b['open'] for _,_,b in chosen]
                pg=100*green/n if n else None;pb=100*base_green/base_n if base_n else None
                output.append({'start_year':year,'target':'C'+str(target),'predictor':'C'+str({1:3,2:1,3:2}[target]),'condition':name,'label':LABELS[name],'n':n,'green':green,'red':n-green,'green_pct':pg,'red_pct':100-pg if n else None,'baseline_n':base_n,'baseline_green':base_green,'baseline_green_pct':pb,'green_change_pp':pg-pb if n else None,'mean_body_points':statistics.mean(body) if n else None,'median_body_points':statistics.median(body) if n else None,'below_50':n<50,'event_sha256':hashlib.sha256(','.join(str(i) for i,_,_ in chosen).encode()).hexdigest()})
    days=Counter(x['date'] for x in rows)
    audit={'input_sha256':CONFIG['input_sha256'],'rows':len(rows),'non_quarter_point_rows_preserved':sum(any(not (x[k]*4).is_integer() for k in ['open','high','low','close']) for x in rows),'first_timestamp':rows[0]['time'].isoformat(),'last_timestamp':rows[-1]['time'].isoformat(),'observed_trading_dates':len(days),'complete_three_row_dates':sum(v==3 for v in days.values()),'incomplete_dates':sum(v!=3 for v in days.values()),'adjacent_pairs':len(rows)-1,'invalid_transitions':invalid,'valid_transition_dojis':dojis,'non_doji_valid_outcomes':len(events),'no_following_row':1,'summary_rows':len(output),'condition_target_comparisons_primary':24,'overlapping_periods':True,'new_validation':False,'original_full_search_reproduced':False,'all_source_candles_retain_vendor_aggregation':True}
    return output,audit

def write(rows,audit,out):
    out.mkdir(parents=True,exist_ok=True)
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',type=Path,default=ROOT/'results');args=p.parse_args()
    rows,audit=summarize(load(args.input));write(rows,audit,args.output)
    print(json.dumps(audit,indent=2))
    for x in rows:
        if x['start_year']==2010 and x['condition'] in ['all','three_red','five_lower_lows','cross_above_sma20']:
            print(x['target'],x['condition'],x['green'],x['n'],round(x['green_pct'],4),round(x['green_change_pp'],4))
if __name__=='__main__':main()
