"""Independent Decimal/vector checks against the fresh summary. No p-values."""
import argparse,csv,hashlib,json,math,statistics
from decimal import Decimal as D
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NAMES=['all','current_red','current_green','three_red','three_green','five_lower_lows','five_higher_highs','cross_above_sma20','cross_below_sma20']
def color(o,c):return 1 if c>o else -1 if c<o else 0
def flags(rows,i):
    out={'all':True,'current_red':rows[i]['color']==-1,'current_green':rows[i]['color']==1}
    for k,sign in [('three_red',-1),('three_green',1)]:out[k]=None if i<2 else [r['color'] for r in rows[i-2:i+1]]==[sign]*3
    for k,f,sign in [('five_lower_lows','low',-1),('five_higher_highs','high',1)]:
        out[k]=None if i<5 else all(color(rows[j-1][f],rows[j][f])==sign for j in range(i-4,i+1))
    if i<20:out.update(cross_above_sma20=None,cross_below_sma20=None)
    else:
        # Compare 20*close with the sum: independent exact Decimal arithmetic.
        a=20*rows[i]['close']-sum(r['close'] for r in rows[i-19:i+1])
        b=20*rows[i-1]['close']-sum(r['close'] for r in rows[i-20:i])
        out.update(cross_above_sma20=a>0 and b<=0,cross_below_sma20=a<0 and b>=0)
    return out

def fixtures():
    from reproduce import condition,transition
    r=[dict(open=10,close=9,high=20-j,low=10-j,color=-1) for j in range(6)]
    assert condition(r,1,'three_red') is None and flags(r,1)['three_red'] is None
    assert condition(r,2,'three_red') and flags(r,2)['three_red']
    r[1].update(close=10,color=0)
    assert not condition(r,2,'three_red') and not flags(r,2)['three_red']
    assert condition(r,4,'five_lower_lows') is None and flags(r,4)['five_lower_lows'] is None
    assert condition(r,5,'five_lower_lows') and flags(r,5)['five_lower_lows']
    r[4]['low']=r[3]['low'];assert not condition(r,5,'five_lower_lows') and not flags(r,5)['five_lower_lows']
    r=[dict(open=D(10),close=D(10),high=D(11),low=D(9),color=0) for _ in range(21)];r[-1]['close']=D(11)
    assert condition(r,20,'cross_above_sma20') and flags(r,20)['cross_above_sma20']
    r[-1]['close']=D(9);assert condition(r,20,'cross_below_sma20') and flags(r,20)['cross_below_sma20']
    r[-1]['close']=D(10);assert not condition(r,20,'cross_below_sma20') and not flags(r,20)['cross_above_sma20']
    a={'slot':1,'date':datetime(2026,1,2).date()};b={'slot':2,'date':datetime(2026,1,3).date()};assert not transition(a,b)
    assert transition({'slot':3,'date':a['date']},{'slot':1,'date':b['date']})
    assert not transition({'slot':3,'date':a['date']},{'slot':2,'date':a['date']})
    return 12

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);args=p.parse_args()
    config=json.loads((ROOT/'config.json').read_text());raw=Path(args.input).read_bytes();assert hashlib.sha256(raw).hexdigest()==config['input_sha256']
    rows=[]
    for x in csv.DictReader(raw.decode('utf-8-sig').splitlines()):
        t=datetime.fromisoformat(x['time']);v={k:D(x[k]) for k in ['open','close','high','low']}
        rows.append({**v,'hour':t.hour,'year':t.year,'day':t.date()+timedelta(days=t.hour==18),'color':color(v['open'],v['close'])})
    masks=[flags(rows,i) for i in range(len(rows))]
    events=[]
    for i in range(len(rows)-1):
        a,b=rows[i:i+2]
        ok=((a['hour'],b['hour']) in [(18,2),(2,10)] and a['day']==b['day']) or (a['hour'],b['hour'])==(10,18)
        if ok and b['color']:events.append(i)
    saved=list(csv.DictReader((ROOT/'results/summary.csv').open(encoding='utf-8')));checks=0
    for x in saved:
        y=int(x['start_year']);hour={'C1':18,'C2':2,'C3':10}[x['target']];name=x['condition']
        eligible=[i for i in events if rows[i]['year']>=y and rows[i+1]['hour']==hour and masks[i][name] is not None]
        hit=[i for i in eligible if masks[i][name]];n=len(hit);g=sum(rows[i+1]['color']==1 for i in hit);bn=len(eligible);bg=sum(rows[i+1]['color']==1 for i in eligible)
        for k,v in [('n',n),('green',g),('red',n-g),('baseline_n',bn),('baseline_green',bg)]:assert int(x[k])==v,(x['target'],name,k);checks+=1
        body=[rows[i+1]['close']-rows[i+1]['open'] for i in hit]
        expected={'green_pct':D(100)*g/n,'red_pct':D(100)*(n-g)/n,'baseline_green_pct':D(100)*bg/bn,'green_change_pp':D(100)*g/n-D(100)*bg/bn,'mean_body_points':statistics.mean(body),'median_body_points':statistics.median(body)}
        for k,v in expected.items():assert math.isclose(float(x[k]),float(v),abs_tol=1e-9,rel_tol=1e-11),(y,name,k);checks+=1
        assert x['event_sha256']==hashlib.sha256(','.join(map(str,hit)).encode()).hexdigest();checks+=1
    # All nine baseline rows reconcile to the recovered workbook, not just rounded rates.
    expected={(2000,'C1'):(3477,6566),(2000,'C2'):(3510,6717),(2000,'C3'):(3689,6769),(2010,'C1'):(2206,4145),(2010,'C2'):(2256,4212),(2010,'C3'):(2353,4223),(2020,'C1'):(885,1656),(2020,'C2'):(915,1674),(2020,'C3'):(919,1671)}
    for x in saved:
        if x['condition']=='all':assert (int(x['green']),int(x['n']))==expected[(int(x['start_year']),x['target'])]
    record={'status':'passed','summary_rows':len(saved),'independent_numeric_and_fingerprint_checks':checks,'baseline_rows_matching_recovered_workbook':9,'synthetic_mechanics_assertions':fixtures(),'independent_method':'Decimal parsing and vector flags; integer comparisons to rolling sums; separate event filtering and summary arithmetic. Fixtures also call production mechanics. No production loader, transition filter or condition loop used for the full-file check.','scope':'Stated historical color rules only; not original broad-search p/q-values, actual execution or unseen-date validation.'}
    (ROOT/'results/verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
