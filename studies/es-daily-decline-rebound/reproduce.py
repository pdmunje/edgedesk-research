"""Daily ES decline recheck. Summarized chart changes, not executed trades."""
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path
from datetime import date
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'config.json').read_text())
def load(path):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CONFIG['input_sha256']:raise ValueError('Source fingerprint mismatch')
    rows=[]
    for x in csv.DictReader(raw.decode('utf-8-sig').splitlines()):
        d=date.fromisoformat(x['time']);v={k:float(x[k]) for k in ['open','high','low','close']}
        if not all(math.isfinite(z) and z>0 for z in v.values()):raise ValueError('Missing/nonpositive/nonfinite price')
        if not v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high']:raise ValueError('Invalid OHLC')
        if rows and d<=rows[-1]['date']:raise ValueError('Unordered/duplicate date')
        rows.append({'date':d,**v})
    return rows

def condition(rows,i,family,k):
    if family=='all':return True
    need=k-1 if family=='red_candles' else k
    if i<need:return None
    if family=='red_candles':return all(rows[j]['close']<rows[j]['open'] for j in range(i-k+1,i+1))
    key={'lower_closes':'close','lower_highs':'high'}[family]
    return all(rows[j][key]<rows[j-1][key] for j in range(i-k+1,i+1))

def measure(rows,indices):
    green=sum(rows[i+1]['close']>rows[i+1]['open'] for i in indices);red=sum(rows[i+1]['close']<rows[i+1]['open'] for i in indices)
    n=len(indices);m=green+red
    out={'all_outcomes':n,'non_doji_outcomes':m,'green':green,'red':red,'doji':n-m,'green_pct':100*green/m if m else None}
    arrays={'body_points':[rows[i+1]['close']-rows[i+1]['open'] for i in indices],'gap_points':[rows[i+1]['open']-rows[i]['close'] for i in indices],'close_change_points':[rows[i+1]['close']-rows[i]['close'] for i in indices],'body_pct':[100*(rows[i+1]['close']/rows[i+1]['open']-1) for i in indices],'close_change_pct':[100*(rows[i+1]['close']/rows[i]['close']-1) for i in indices]}
    for name,values in arrays.items():
        out[name+'_mean']=statistics.mean(values) if n else None;out[name+'_median']=statistics.median(values) if n else None
    out['first_predictor']=rows[indices[0]]['date'].isoformat() if n else None;out['last_predictor']=rows[indices[-1]]['date'].isoformat() if n else None
    out['event_sha256']=hashlib.sha256(','.join(map(str,indices)).encode()).hexdigest()
    return out

def summarize(rows):
    result=[]
    for start in CONFIG['period_starts']:
        pool=[i for i in range(len(rows)-1) if rows[i]['date'].isoformat()>=start]
        for family,k in [('all',0),*[(f,k) for f in CONFIG['families'] for k in CONFIG['lengths']]]:
            eligible=[i for i in pool if condition(rows,i,family,k) is not None];selected=[i for i in eligible if condition(rows,i,family,k)]
            baseline=measure(rows,eligible);r={'period_start':start,'family':family,'length':k,**measure(rows,selected),'baseline_all_outcomes':baseline['all_outcomes'],'baseline_non_doji':baseline['non_doji_outcomes'],'baseline_green':baseline['green'],'baseline_green_pct':baseline['green_pct'],'green_change_pp':None,'baseline_body_points_mean':baseline['body_points_mean']}
            if r['green_pct'] is not None:r['green_change_pp']=r['green_pct']-r['baseline_green_pct']
            result.append(r)
    audit={'rows':len(rows),'input_sha256':CONFIG['input_sha256'],'first_date':rows[0]['date'].isoformat(),'last_date':rows[-1]['date'].isoformat(),'adjacent_pairs':len(rows)-1,'no_following_target':1,'non_quarter_point_rows_preserved':sum(any(not (r[k]*4).is_integer() for k in ['open','high','low','close']) for r in rows),'weekend_rows':sum(r['date'].weekday()>4 for r in rows),'full_file_target_dojis':sum(rows[i+1]['close']==rows[i+1]['open'] for i in range(len(rows)-1)),'summary_rows':len(result),'primary_patterns':12,'overlapping_periods_and_nested_lengths':True,'new_validation_dates':False,'broad_original_search_reproduced':False,'missing_dates_filled':False,'date_only_vendor_labels':True}
    return result,audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);args=p.parse_args();rows,audit=summarize(load(args.input));out=ROOT/'results';out.mkdir(exist_ok=True)
    with (out/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8');print(json.dumps(audit,indent=2))
    for r in rows:
        if r['period_start']=='2010-01-01' and r['length'] in [0,4]:print(r)
if __name__=='__main__':main()
