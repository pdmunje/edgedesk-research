"""Independent Decimal and ISO-calendar check; production used only for fixtures."""
import argparse,csv,hashlib,json,math
from collections import Counter
from datetime import date,timedelta
from decimal import Decimal as D
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def read_input(path,expected):
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
    with Path(path).open(encoding='utf-8-sig',newline='') as f:raw=list(csv.DictReader(f))
    data=[]
    for r in raw:
        dt=date.fromisoformat(r['time']);v=tuple(D(r[k]) for k in ['open','high','low','close'])
        assert all(x.is_finite() and x>0 for x in v) and v[2]<=min(v[0],v[3])<=max(v[0],v[3])<=v[1]
        assert not data or dt>data[-1][0];data.append((dt,*v))
    return data

def sign(x):return 'G' if x>0 else 'R' if x<0 else 'D'
def average(x):return sum(x)/len(x)
def middle(x):
    s=sorted(x);i=len(s)//2
    return s[i] if len(s)%2 else (s[i-1]+s[i])/2

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--daily',required=True);ap.add_argument('--weekly',required=True);a=ap.parse_args();config=json.loads((ROOT/'config.json').read_text());daily=read_input(a.daily,config['daily_sha256']);weekly=read_input(a.weekly,config['weekly_sha256'])
    groups={}
    for r in daily:groups.setdefault(r[0].isocalendar()[:2],[]).append(r)
    assert len(groups)==len(weekly)==1504
    wm={r[0].isocalendar()[:2]:r for r in weekly};assert len(wm)==len(weekly) and set(wm)==set(groups)
    for key,ds in groups.items():assert tuple(wm[key][1:])==(ds[0][1],max(r[2] for r in ds),min(r[3] for r in ds),ds[-1][4])
    complete=[ds for _,ds in sorted(groups.items()) if len(ds)==5];assert len(complete)==1274
    actual=list(csv.DictReader((ROOT/'results/summary.csv').open(newline='',encoding='utf-8-sig')));checks=0
    for row in actual:
        k=int(row['stage']);prefix=row['prefix'];year={'full':0,'2010_onward':2010,'2020_onward':2020}[row['period']]
        candidates=[ds for ds in complete if (ds[0][0]-timedelta(days=ds[0][0].weekday())).year>=year];selected=[ds for ds in candidates if prefix=='ALL' or ''.join(sign(r[4]-r[1]) for r in ds[:k])==prefix];n=len(selected)
        expected={'n':n};week=[ds[-1][4]-ds[0][1] for ds in selected];elapsed=[ds[k-1][4]-ds[0][1] for ds in selected];remaining=[ds[-1][4]-ds[k-1][4] for ds in selected];no=[ds[-1][4]-ds[k][1] for ds in selected];rp=[100*(ds[-1][4]-ds[k-1][4])/ds[k-1][4] for ds in selected];np=[100*(ds[-1][4]-ds[k][1])/ds[k][1] for ds in selected];nextday=[ds[k][4]-ds[k][1] for ds in selected]
        for name,values,labels in [('week',week,['green','red','doji']),('remaining',remaining,['up','down','flat']),('next_open',no,['up','down','flat']),('next_day',nextday,['green','red','doji'])]:
            for code,label in zip(['G','R','D'],labels):expected[name+'_'+label]=sum(sign(x)==code for x in values)
        expected['week_green_pct']=100*D(expected['week_green'])/n
        for name,values,percent in [('week',week,None),('remaining',remaining,rp),('next_open',no,np)]:
            expected[name+'_mean_points']=average(values);expected[name+'_median_points']=middle(values)
            if percent is not None:
                expected[name+'_mean_pct']=average(percent);expected[name+'_median_pct']=middle(percent);expected[name+'_up_pct']=100*D(expected[name+'_up'])/n
        expected['elapsed_mean_points']=average(elapsed)
        for key,value in expected.items():assert math.isclose(float(row[key]),float(value),rel_tol=1e-11,abs_tol=1e-9),(row['period'],k,prefix,key);checks+=1
        assert row['event_fingerprint']==hashlib.sha256('\n'.join(str(ds[0][0]-timedelta(days=ds[0][0].weekday())) for ds in selected).encode()).hexdigest();checks+=1
        assert all(w==e+r for w,e,r in zip(week,elapsed,remaining))
    for period in config['periods']:
        for k in range(1,5):
            rows=[x for x in actual if x['period']==period and int(x['stage'])==k];baseline=next(x for x in rows if x['prefix']=='ALL');parts=[x for x in rows if x['prefix']!='ALL'];assert sum(int(x['n']) for x in parts)==int(baseline['n']);assert all(len(x['prefix'])==k for x in parts)
    timing=list(csv.DictReader((ROOT/'results/high-low-timing.csv').open()))
    for row in timing:
        i=int(row['session'])-1
        for field,col in [('first_week_high',2),('first_week_low',3)]:
            count=sum(next(j for j,r in enumerate(ds) if r[col]==(max if col==2 else min)(x[col] for x in ds))==i for ds in complete);assert int(row[field])==count;checks+=1
    audit=json.loads((ROOT/'results/audit.json').read_text());assert audit['daily_rows_per_week']=={str(k):v for k,v in sorted(Counter(map(len,groups.values())).items())};assert audit['weekly_non_monday_labels']==sum(r[0].weekday()!=0 for r in weekly)
    import reproduce as prod
    assert [prod.color(D(1),D(x)) for x in [2,0,1]]==['G','R','D']
    start=date(2021,1,4);fixture=[]
    for i,(o,c,h,l) in enumerate([(100,110,120,95),(111,111,115,90),(111,109,120,100),(109,108,112,99),(108,105,110,90)]):fixture.append({'date':start+timedelta(days=i),**{n:D(v) for n,v in zip(['open','close','high','low'],[o,c,h,l])}})
    wk={'date':start+timedelta(days=1),'open':D(100),'high':D(120),'low':D(90),'close':D(105)}
    assert list(prod.group_and_match(fixture,[wk]))==[start]
    out,t,au=prod.calculate(fixture,[wk]);r=next(x for x in out if x['period']=='full' and x['stage']==1 and x['prefix']=='ALL');assert r['week_mean_points']==5 and r['elapsed_mean_points']==10 and r['remaining_mean_points']==-5 and r['next_open_mean_points']==-6
    assert t[0]['first_week_high']==1 and t[1]['first_week_low']==1 and au['high_tied_weeks']==au['low_tied_weeks']==1
    assert len(prod.group_and_match(fixture[:4],[{**wk,'close':D(108)}])[start])==4
    for weekly_fixture in [[{**wk,'close':D(104)}],[wk,{**wk,'date':start}]]:
        try:prod.group_and_match(fixture,weekly_fixture)
        except ValueError:pass
        else:raise AssertionError('Mismatch or duplicate week was accepted')
    result={'summary_rows':len(actual),'independent_numeric_and_event_checks':checks,'weekly_ohlc_exact_matches':len(groups),'partition_groups_checked':12,'boundary_groups':7,'coverage':'Own Decimal loader, ISO-week grouping, prefix selection, outcome arithmetic, medians, percentages and ordered event hashes. Production called only by made-up fixtures.','limitations':'Agreement with these definitions does not verify exchange timestamps, future eligibility, vendor adjustments, executable fills or unseen-date performance.'};(ROOT/'results/verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
