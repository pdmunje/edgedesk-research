"""Independent Decimal/streak verification of all summarized daily patterns."""
import argparse,csv,hashlib,json,math,statistics
from datetime import date
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def fixtures():
    from reproduce import condition,measure
    rows=[dict(close=v,open=v+1,high=v+2,low=v-1) for v in [14,13,12,11,10]]
    assert condition(rows,3,'lower_closes',4) is None
    assert condition(rows,4,'lower_closes',4)
    assert condition(rows,3,'red_candles',4)
    rows[2]['close']=rows[1]['close'];assert not condition(rows,4,'lower_closes',4)
    rows[2]['open']=rows[2]['close'];assert not condition(rows,3,'red_candles',4)
    for i,r in enumerate(rows):r['date']=date(2020,1,i+1)
    rows=[dict(date=date(2020,1,1),open=101,close=100,high=102,low=99),dict(date=date(2020,1,2),open=103,close=103,high=104,low=102)]
    m=measure(rows,[0]);assert m['all_outcomes']==1 and m['non_doji_outcomes']==0 and m['green_pct'] is None
    assert m['body_points_mean']==0 and m['gap_points_mean']==3 and m['close_change_points_mean']==3
    rows[-1].update(open=104,close=102);m=measure(rows,[0]);assert m['red']==1 and m['body_points_mean']==-2 and m['close_change_points_mean']==2
    assert not condition(rows,1,'red_candles',3)
    return 9

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);args=p.parse_args();raw=Path(args.input).read_bytes();config=json.loads((ROOT/'config.json').read_text());assert hashlib.sha256(raw).hexdigest()==config['input_sha256']
    rows=[]
    for x in csv.DictReader(raw.decode('utf-8-sig').splitlines()):rows.append({'date':date.fromisoformat(x['time']),**{k:D(x[k]) for k in ['open','high','low','close']}})
    streaks={key:[] for key in ['lower_closes','lower_highs','red_candles']};run={key:0 for key in streaks}
    for i,r in enumerate(rows):
        for key in run:
            yes=(r['close']<r['open']) if key=='red_candles' else (i>0 and r['close' if key=='lower_closes' else 'high']<rows[i-1]['close' if key=='lower_closes' else 'high'])
            run[key]=run[key]+1 if yes else 0;streaks[key].append(run[key])
    saved=list(csv.DictReader((ROOT/'results/summary.csv').open(encoding='utf-8')));checks=0
    for s in saved:
        start=date.fromisoformat(s['period_start']);family=s['family'];k=int(s['length']);minimum=0 if family=='all' else k-1 if family=='red_candles' else k
        pool=[i for i in range(minimum,len(rows)-1) if rows[i]['date']>=start];hit=[i for i in pool if family=='all' or streaks[family][i]>=k]
        g=sum(rows[i+1]['close']>rows[i+1]['open'] for i in hit);red=sum(rows[i+1]['close']<rows[i+1]['open'] for i in hit);bn=sum(rows[i+1]['close']!=rows[i+1]['open'] for i in pool);bg=sum(rows[i+1]['close']>rows[i+1]['open'] for i in pool)
        expected={'all_outcomes':len(hit),'non_doji_outcomes':g+red,'green':g,'red':red,'doji':len(hit)-g-red,'baseline_all_outcomes':len(pool),'baseline_non_doji':bn,'baseline_green':bg}
        for name,v in expected.items():assert int(s[name])==v,(family,k,name);checks+=1
        scalar={'green_pct':D(100)*g/(g+red),'baseline_green_pct':D(100)*bg/bn,'green_change_pp':D(100)*(D(g)/(g+red)-D(bg)/bn),'baseline_body_points_mean':statistics.mean(rows[i+1]['close']-rows[i+1]['open'] for i in pool)}
        for name,v in scalar.items():assert math.isclose(float(s[name]),float(v),rel_tol=1e-10,abs_tol=1e-9),(family,k,name);checks+=1
        values={'body_points':[rows[i+1]['close']-rows[i+1]['open'] for i in hit],'gap_points':[rows[i+1]['open']-rows[i]['close'] for i in hit],'close_change_points':[rows[i+1]['close']-rows[i]['close'] for i in hit],'body_pct':[100*(rows[i+1]['close']-rows[i+1]['open'])/rows[i+1]['open'] for i in hit],'close_change_pct':[100*(rows[i+1]['close']-rows[i]['close'])/rows[i]['close'] for i in hit]}
        for name,arr in values.items():
            for suffix,v in [('mean',statistics.mean(arr)),('median',statistics.median(arr))]:assert math.isclose(float(s[name+'_'+suffix]),float(v),rel_tol=1e-10,abs_tol=1e-9),(family,k,name,suffix);checks+=1
        assert math.isclose(float(s['body_points_mean'])+float(s['gap_points_mean']),float(s['close_change_points_mean']),abs_tol=1e-9);checks+=1
        assert s['first_predictor']==rows[hit[0]]['date'].isoformat() and s['last_predictor']==rows[hit[-1]]['date'].isoformat();checks+=1
        assert s['event_sha256']==hashlib.sha256(','.join(map(str,hit)).encode()).hexdigest();checks+=1
    focus=next(s for s in saved if s['period_start']=='2010-01-01' and s['family']=='lower_closes' and s['length']=='4')
    assert (int(focus['all_outcomes']),int(focus['non_doji_outcomes']),int(focus['green']))==(149,148,91)
    record={'status':'passed','summary_rows':len(saved),'independent_numeric_date_identity_fingerprint_checks':checks,'synthetic_boundary_assertions':fixtures(),'independent_method':'Own Decimal parser, cumulative streak arrays and summary calculation; no production loader, pattern-window loop or full-file summarizer reused. Fixtures exercise production functions.','scope':'Previously explored source counts and chart changes only; original full search/inference, later-date validation and actual fills unverified.'}
    (ROOT/'results/verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record,indent=2))
if __name__=='__main__':main()
